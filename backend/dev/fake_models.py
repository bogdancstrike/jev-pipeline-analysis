"""GPU-less stand-ins for the model engines, for UI/backend work on a laptop and for the test
suite (which calls the pure functions directly through httpx.MockTransport).

  uvicorn dev.fake_models:systemone --port 9100 &   # a System One engine (as laya / kev / qwen)
  uvicorn dev.fake_models:extractor --port 9200 &   # the GLiNER2 extractor
  ENGINES_PATH=dev/engines.dev.yaml MODULES_DIR=../config/modules SAMPLES_DIR=../samples \
  uvicorn app.main:create_app --factory --port 8000

Answers are deterministic and dumb, but exercise every code path: a choice picks the option
whose key/description words appear most in the document (ties broken by a hash), a yes/no
over two reports says "yes" when they share several capitalized words, entities are
capitalized words, relations link consecutive entities.
"""
import asyncio
import hashlib
import json
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

H = {"x-request-id": "req_" + "0" * 32}
_WORD = re.compile(r"\w{4,}")
_CAPS = re.compile(r"\b[A-ZĂÂÎȘȚŞŢ][\w-]{2,}")


def _doc(state) -> str:
    return state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)


def _pick(doc: str, key: str, criteria: dict) -> tuple[str, dict[str, float]]:
    keys = list(criteria)
    low = doc.lower()
    hits = {k: sum(low.count(w) for w in _WORD.findall(f"{k.replace('_', ' ')} {criteria[k] or ''}".lower()))
            for k in keys}
    if max(hits.values()) == 0:
        pick = keys[int(hashlib.md5((doc + key).encode()).hexdigest(), 16) % len(keys)]
    else:
        pick = max(keys, key=lambda k: hits[k])
    p = {k: 0.3 / (len(keys) - 1) for k in keys}
    p[pick] = 0.7
    return pick, p


def decide(body: dict, max_state_chars: int = 0) -> tuple[int, dict]:
    """One /v1/systemone request. `max_state_chars` > 0 behaves like an engine that 422s."""
    doc = _doc(body["state"])
    if max_state_chars and len(doc) > max_state_chars:
        return 422, {"detail": [{"loc": ["body", "state"], "type": "too_long",
                                 "msg": "state + question over the sequence limit"}]}
    answers = {}
    for key, q in body["questions"].items():
        if q["type"] == "noul":
            st = body["state"] if isinstance(body["state"], dict) else {}
            vals = list(st.values())[:2]
            a, b = (set(_CAPS.findall(str(v))) for v in vals) if len(vals) == 2 else (set(), set())
            answers[key] = {"type": "noul", "noul": 0.85 if len(a & b) >= 3 else 0.15}
            continue
        pick, p = _pick(doc, key, q["criteria"])
        answers[key] = {"type": "choice", "choice": pick, "confidence": 0.7, "probabilities": p}
    return 200, {"model": "local/fake-engine", "answers": answers}


def decide_batch(body: dict) -> tuple[int, dict]:
    results = []
    for s in body["states"]:
        status, out = decide({**body, "state": s})
        if status != 200:
            return status, out
        results.append(out)
    return 200, {"results": results, "total_usage": {"input_tokens": 0, "output_tokens": 0}}


def _entities(text: str, labels: list[str]) -> list[dict]:
    pool = labels[:4] or ["person"]
    return [{"start": m.start(), "end": m.end(), "text": m.group(), "label": pool[i % len(pool)], "score": 0.8}
            for i, m in enumerate(_CAPS.finditer(text))]


def extract(body: dict) -> dict:
    """One /v1/extract request of the GLiNER2 extractor service."""
    task, spec = body["task"], body["spec"]
    out = []
    for t in body["texts"]:
        if task == "entities":
            out.append(_entities(t, list(spec)))
        elif task == "relations":
            ents, types = _entities(t, ["x"]), list(spec)
            out.append([{"relation": types[i % len(types)], "score": 0.8,
                         "head": {k: a[k] for k in ("text", "start", "end")},
                         "tail": {k: b[k] for k in ("text", "start", "end")}}
                        for i, (a, b) in enumerate(zip(ents, ents[1:])) if i < 3])
        elif task == "classify":
            res = {}
            for name, cfg in spec.items():
                labels = cfg["labels"] if isinstance(cfg, dict) else cfg
                crit = labels if isinstance(labels, dict) else {k: "" for k in labels}
                pick, _ = _pick(t, name, crit)
                res[name] = {"label": pick, "confidence": 0.7}
            out.append(res)
        else:  # structures
            caps = _CAPS.findall(t)
            out.append({rec: [{f.split("::")[0]: {"text": caps[k % len(caps)], "confidence": 0.8}
                               for k, f in enumerate(fields)}] if caps else []
                        for rec, fields in spec.items()})
    return {"results": out, "latency_ms": 1.0}


# ------------------------------------------------------------------ HTTP apps for dev
systemone = FastAPI()
extractor = FastAPI()


@systemone.get("/health")
@systemone.get("/readyz")
async def s_ready():
    return {"status": "ok", "engine": "local/fake-engine"}


@systemone.post("/v1/systemone")
async def s_one(req: Request):
    await asyncio.sleep(0.01)
    status, body = decide(await req.json())
    return JSONResponse(status_code=status, headers=H, content=body)


@systemone.post("/v1/systemone/batch")
async def s_batch(req: Request):
    await asyncio.sleep(0.02)
    status, body = decide_batch(await req.json())
    return JSONResponse(status_code=status, headers=H, content=body)


@extractor.get("/readyz")
async def x_ready():
    return {"status": "ready", "engine": "gliner2", "models": {"fake": "fake/gliner2"}, "device": "cpu"}


@extractor.post("/v1/extract")
async def x_extract(req: Request):
    await asyncio.sleep(0.02)
    return extract(await req.json())
