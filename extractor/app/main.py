"""GLiNER2 as a small GPU service: entities, relations, classification, structured fields.

Design:
- One process holds every configured checkpoint (EXTRACTOR_MODELS: alias -> repo) and one GPU
  lock. Batching beats concurrency on a single GPU: callers send N texts, we run batched passes.
- Per-text routing: a request names a model alias, or a route like {"en": "decide",
  "*": "decide-multi"}; texts are grouped by detected language and each group runs on its
  checkpoint (GLiNER2.5-Decide is English-only; its multilingual twin covers the rest).
- Long documents use gliner2's own chunking (`batch_*_long`): overlapping word windows,
  spans remapped to the original string, duplicates merged.
- Outputs are normalized to flat, typed shapes so callers never parse gliner2's formats.
"""
import asyncio
import hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import torch
from fastapi import Depends, FastAPI, HTTPException, Request
from gliner2 import AutoExtractor
from py3langid.langid import MODEL_FILE, LanguageIdentifier
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("extractor")


def _secret(name: str) -> str:
    path = os.environ.get(f"{name}_FILE")
    if path and Path(path).exists():
        return Path(path).read_text().strip()
    if v := os.environ.get(name):
        return v
    raise RuntimeError(f"set {name} or {name}_FILE")


API_KEY = _secret("EXTRACTOR_API_KEY")
MODELS: dict[str, str] = json.loads(os.environ["EXTRACTOR_MODELS"])
GPU_FRACTION = float(os.environ.get("EXTRACTOR_GPU_MEM_FRACTION", "0.35"))
# Above this much reserved-but-idle memory, hand the cache back after a request: the card is
# shared with Laya, which falls back to the CPU (30x slower) when it cannot allocate.
RELEASE_ABOVE_MB = int(os.environ.get("EXTRACTOR_RELEASE_ABOVE_MB", "2500"))
# bf16 halves weight memory (three checkpoints fit in ~2 GB) at no measurable cost for encoders
# on Ampere+. float32 on CPU, where bf16 matmuls are slow.
DTYPE = os.environ.get("EXTRACTOR_DTYPE", "bfloat16")
# gliner2 load options, e.g. {"attention_backend": "disentangled_flash", "disentangled_flash_packed": true}
# or {"compile": true}. Measured choices are documented in docs/BENCHMARKS.md.
LOAD_OPTIONS: dict[str, Any] = json.loads(os.environ.get("EXTRACTOR_LOAD_OPTIONS", "{}"))
MAX_TEXTS = 128
MAX_CHARS = 100_000
STATE: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.time()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        # Hard cap so the extractor can never starve the decision models sharing the card.
        torch.cuda.set_per_process_memory_fraction(GPU_FRACTION)
        torch.backends.cuda.matmul.allow_tf32 = True
    models = {}
    for alias, repo in MODELS.items():
        dtype = getattr(torch, DTYPE) if device == "cuda" else torch.float32
        if device == "cuda" and LOAD_OPTIONS:
            # Attention backends (disentangled_flash) bind to the device they are enabled on:
            # load straight onto the GPU, and only cast dtype afterwards.
            m = AutoExtractor.from_pretrained(repo, map_location=device, **LOAD_OPTIONS)
            models[alias] = m.to(dtype=dtype).eval()
        else:
            m = AutoExtractor.from_pretrained(repo)
            models[alias] = m.to(device=device, dtype=dtype).eval()
        log.info("loaded %s = %s", alias, repo)
    lid = LanguageIdentifier.from_pickled_model(MODEL_FILE, norm_probs=True)
    STATE.update(models=models, device=device, lock=asyncio.Lock(), lid=lid)
    # Warm-up: the first CUDA call pays kernel/JIT costs; don't bill that to request #1.
    for m in models.values():
        await asyncio.to_thread(m.batch_extract_entities, ["Warm-up text about Bucharest."], ["city"])
    log.info("extractor ready on %s in %.1fs: %s", device, time.time() - t0, MODELS)
    STATE["ready"] = True
    yield


app = FastAPI(title="extractor", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def auth(request: Request) -> None:
    h = request.headers.get("authorization", "")
    if not h.startswith("Bearer ") or not hmac.compare_digest(h[7:].encode(), API_KEY.encode()):
        raise HTTPException(401, "invalid token")


class ExtractRequest(BaseModel):
    task: Literal["entities", "relations", "classify", "structures"]
    texts: list[str] = Field(..., min_length=1, max_length=MAX_TEXTS)
    # entities: {label: description} | [label]; relations: {type: description} | [type];
    # classify: {task: {"labels": {label: description}, "multi_label": bool}};
    # structures: {record: ["field::dtype::description", ...]}
    spec: dict | list
    model: str | dict[str, str] = Field("*", description="alias, or {lang: alias, '*': alias}")
    threshold: float = Field(0.5, ge=0.0, le=1.0)
    chunk_size: int = Field(384, ge=64, le=2048)
    chunk_overlap: int = Field(64, ge=0, le=512)
    batch_size: int = Field(8, ge=1, le=64)


def _route(texts: list[str], model: str | dict[str, str]) -> dict[str, list[int]]:
    """alias -> indices of the texts it handles."""
    models = STATE["models"]
    if isinstance(model, str):
        alias = next(iter(models)) if model == "*" else model
        if alias not in models:
            raise HTTPException(422, f"unknown model {alias!r}; loaded: {list(models)}")
        return {alias: list(range(len(texts)))}
    unknown = [a for a in model.values() if a not in models]
    if unknown:
        raise HTTPException(422, f"unknown model(s) {unknown}; loaded: {list(models)}")
    groups: dict[str, list[int]] = {}
    for i, t in enumerate(texts):
        lang = STATE["lid"].classify(t[:2000])[0] if t.strip() else "*"
        groups.setdefault(model.get(lang, model.get("*", next(iter(models)))), []).append(i)
    return groups


def _entities(out: dict) -> list[dict]:
    spans = []
    for label, items in (out.get("entities") or {}).items():
        for e in items or []:
            if isinstance(e, dict) and "start" in e:
                spans.append({"start": e["start"], "end": e["end"], "text": e["text"], "label": label,
                              "score": round(float(e.get("confidence", 1.0)), 4)})
    return sorted(spans, key=lambda s: (s["start"], -s["end"]))


def _relations(out: dict) -> list[dict]:
    rels = []
    for rel, items in (out.get("relation_extraction") or {}).items():
        for r in items or []:
            h, t = r.get("head") or {}, r.get("tail") or {}
            if not h or not t:
                continue
            score = min(float(h.get("confidence", 1.0)), float(t.get("confidence", 1.0)))
            rels.append({"relation": rel, "score": round(score, 4),
                         "head": {k: h[k] for k in ("text", "start", "end") if k in h},
                         "tail": {k: t[k] for k in ("text", "start", "end") if k in t}})
    return sorted(rels, key=lambda r: -r["score"])


def _run(req: ExtractRequest, model, texts: list[str]) -> list[Any]:
    kw = dict(batch_size=req.batch_size, threshold=req.threshold, include_confidence=True,
              chunk_size=req.chunk_size, chunk_overlap=req.chunk_overlap)
    if req.task == "entities":
        return [_entities(o) for o in model.batch_extract_entities_long(texts, req.spec, include_spans=True, **kw)]
    if req.task == "relations":
        return [_relations(o) for o in model.batch_extract_relations_long(texts, req.spec, include_spans=True, **kw)]
    if req.task == "classify":
        return model.batch_classify_text_long(texts, req.spec, **kw)
    return model.batch_extract_json_long(texts, req.spec, **kw)


def _run_adaptive(req: ExtractRequest, alias: str, texts: list[str]) -> list[Any]:
    """Run, and on CUDA OOM free the cache and retry with half the batch (down to 1).

    Long documents make activation memory vary a lot, so the batch size self-tunes to what
    fits. The size that worked becomes a sticky cap for this (model, task): an OOM costs a
    wasted forward pass, so it must happen once, not on every request.
    """
    caps = STATE.setdefault("bs_cap", {})
    key = (alias, req.task)
    bs = min(req.batch_size, caps.get(key, req.batch_size))
    while True:
        try:
            out = _run(req.model_copy(update={"batch_size": bs}), STATE["models"][alias], texts)
            if bs < req.batch_size:
                caps[key] = bs
            return out
        except torch.OutOfMemoryError:
            torch.cuda.empty_cache()
            if bs == 1:
                raise
            STATE["oom_retries"] = STATE.get("oom_retries", 0) + 1
            log.warning("CUDA OOM on %s/%s at batch_size=%d; capping at %d", alias, req.task, bs, bs // 2)
            bs //= 2


def _predict(req: ExtractRequest) -> list[Any]:
    texts = [t[:MAX_CHARS] for t in req.texts]
    results: list[Any] = [None] * len(texts)
    with torch.inference_mode():
        for alias, idx in _route(texts, req.model).items():
            for i, r in zip(idx, _run_adaptive(req, alias, [texts[i] for i in idx])):
                results[i] = r
    return results


@app.post("/v1/extract", dependencies=[Depends(auth)])
async def extract(req: ExtractRequest):
    if not STATE.get("ready"):
        raise HTTPException(503, "loading", headers={"retry-after": "2"})
    t0 = time.perf_counter()
    async with STATE["lock"]:  # serialize GPU use; the batch inside is the parallelism
        try:
            results = await asyncio.to_thread(_predict, req)
        except (ValueError, TypeError, KeyError) as e:  # a malformed spec, not a server fault
            raise HTTPException(422, f"invalid {req.task} spec: {e}") from e
        finally:
            if STATE["device"] == "cuda" and torch.cuda.memory_reserved() / 2**20 > RELEASE_ABOVE_MB:
                torch.cuda.empty_cache()
    return {"results": results, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    if not STATE.get("ready"):
        raise HTTPException(503, "loading")
    dev = STATE["device"]
    info: dict[str, Any] = {"status": "ready", "engine": "gliner2", "models": MODELS, "device": dev,
                            "load_options": LOAD_OPTIONS,
                            "dtype": DTYPE if dev == "cuda" else "float32"}
    if dev == "cuda":
        info["gpu"] = torch.cuda.get_device_name(0)
        info["vram_reserved_mb"] = round(torch.cuda.memory_reserved() / 2**20)
        info["oom_retries"] = STATE.get("oom_retries", 0)
        info["vram_peak_mb"] = round(torch.cuda.max_memory_allocated() / 2**20)
        info["batch_caps"] = {f"{a}/{t}": bs for (a, t), bs in STATE.get("bs_cap", {}).items()}
    return info
