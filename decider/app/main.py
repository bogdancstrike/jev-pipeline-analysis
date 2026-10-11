"""On-prem decision API (Jev-style /v1/systemone contract) on vLLM + a local AWQ 4-bit model.

POST /v1/systemone {model, state, questions:{key:{type: choice|noul|score, instructions, criteria}}}
  choice -> {choice, confidence, probabilities}   noul -> {noul: P(yes)}
  score  -> {score: E[level], confidence, legend, probabilities}
Errors: 401/403 auth, 422 over budget (never silently truncated), 503 loading.
"""
import asyncio
import hmac
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .engine import EngineError, EngineLoading, VllmEngine
from .prompts import PromptIntegrityError, options_for, render_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("decider")


def _secret(name: str) -> str:
    path = os.environ.get(f"{name}_FILE")
    if path and Path(path).exists():
        return Path(path).read_text().strip()
    if v := os.environ.get(name):
        return v
    raise RuntimeError(f"set {name} or {name}_FILE")


API_KEY = _secret("DECIDER_API_KEY")
MAX_OPTIONS = 128
ENGINE = VllmEngine(os.environ.get("LLM_URL", "http://llm:8000"), _secret("LLM_API_KEY"),
                    os.environ.get("TOKENIZER_PATH", "/opt/tokenizer/tokenizer.json"))
# Operator-trusted text appended after "assistant\n" (e.g. an empty think block for hybrid
# thinking models). Parsed WITH added tokens on purpose; it never contains user input.
_PREFIX = os.environ.get("ASSISTANT_PREFIX", "").encode().decode("unicode_escape")
STATE: dict[str, Any] = {"ready": False, "sem": asyncio.Semaphore(16)}


def _prefix_ids() -> list[int]:
    if not _PREFIX:
        return []
    tok = ENGINE.builder.tok
    tok.encode_special_tokens = False
    try:
        return tok.encode(_PREFIX, add_special_tokens=False).ids
    finally:
        tok.encode_special_tokens = True


async def _startup() -> None:
    while True:
        try:
            await ENGINE.wait_ready()
            STATE["prefix_ids"] = _prefix_ids()
            await ENGINE.measure_prefill()
            STATE["ready"] = True
            log.info("ready: %s max_model_len=%s prefill=%s tok/s", ENGINE.model_name,
                     ENGINE.max_model_len, ENGINE.prompt_tps)
            return
        except EngineError as e:
            if "mismatch" in str(e):
                log.critical("%s -- refusing to serve", e)
                STATE["fatal"] = str(e)
                return
            log.info("waiting for vLLM: %s", e)
            await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_startup())
    yield
    task.cancel()
    await ENGINE.aclose()


app = FastAPI(title="decider", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def request_id(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["x-request-id"] = "req_" + uuid.uuid4().hex
    return resp


def auth(request: Request) -> None:
    h = request.headers.get("authorization", "")
    if not h.lower().startswith("bearer "):
        raise HTTPException(403, {"error_type": "authentication_error", "message": "missing bearer token"})
    if not hmac.compare_digest(h[7:].strip().encode(), API_KEY.encode()):
        raise HTTPException(401, {"error_type": "authentication_error", "message": "invalid token"})


class Question(BaseModel):
    type: Literal["choice", "noul", "score"]
    instructions: str = Field(..., min_length=1, max_length=4000)
    criteria: dict[str, Any] | list[Any] | None = None


class SystemOneRequest(BaseModel):
    model: str = "local-latest"
    state: str | dict | list
    questions: dict[str, Question] = Field(..., min_length=1, max_length=32)


def _bad(key: str, field: str, msg: str, typ: str = "value_error") -> HTTPException:
    loc = ["body", "questions", key] + ([field] if field else [])
    return HTTPException(422, [{"loc": loc, "msg": msg, "type": typ}])


async def _answer(key: str, q: Question, document: str) -> tuple[dict, int, dict]:
    if q.type == "choice" and not isinstance(q.criteria, dict):
        raise _bad(key, "criteria", "choice needs an object of option -> description")
    if q.type == "score" and (not isinstance(q.criteria, list) or not 2 <= len(q.criteria) <= 10):
        raise _bad(key, "criteria", "score needs 2..10 ordered levels")
    opts = options_for(q.type, q.criteria)
    if not 2 <= len(opts) <= MAX_OPTIONS:
        raise _bad(key, "criteria", f"need 2..{MAX_OPTIONS} options")
    try:
        table = ENGINE.option_tokens([k for k, _ in opts])
        prefix = STATE["prefix_ids"]
        q_ids = ENGINE.builder.build("", q.instructions, opts, prefix)
        q_limit = ENGINE.max_model_len // 2
        if len(q_ids) > q_limit:
            raise _bad(key, "", f"Question '{key}' is about {len(q_ids)} tokens, over this model's limit of {q_limit} per question.", "too_long")
        ids = ENGINE.builder.build(document, q.instructions, opts, prefix)
    except ValueError as e:
        raise _bad(key, "criteria", str(e)) from e
    limit = ENGINE.max_model_len - 1 - max(len(t) for t in table.values())
    if len(ids) > limit:
        raise _bad(key, "", f"state + question is about {len(ids)} tokens, over the {limit}-token sequence limit.", "too_long")

    async with STATE["sem"]:
        s = await ENGINE.score(ids, table)
    probs, meta = s.probabilities, {"coverage": s.coverage, "forward_passes": s.forward_passes}
    if q.type == "choice":
        best = max(probs, key=probs.__getitem__)
        return ({"type": "choice", "choice": best, "confidence": round(probs[best], 6),
                 "probabilities": {k: round(probs[k], 6) for k, _ in opts}}, len(ids), meta)
    if q.type == "noul":
        return {"type": "noul", "noul": round(probs["yes"], 6)}, len(ids), meta
    legend = {str(i): str(v) for i, v in enumerate(q.criteria)}
    best = max(probs, key=probs.__getitem__)
    return ({"type": "score", "score": round(sum(int(k) * p for k, p in probs.items()), 4),
             "confidence": round(probs[best], 6), "legend": legend,
             "probabilities": {k: round(probs[k], 6) for k in legend}}, len(ids), meta)


def _unavailable(msg: str = "loading") -> JSONResponse:
    return JSONResponse(status_code=503, headers={"retry-after": "1"},
                        content={"detail": {"error_type": "engine_unavailable", "message": msg}})


@app.post("/v1/systemone", dependencies=[Depends(auth)])
async def systemone(req: SystemOneRequest):
    if not STATE["ready"]:
        return _unavailable(STATE.get("fatal", "loading"))
    t0 = time.perf_counter()
    document = render_state(req.state)
    try:
        results = await asyncio.gather(*(_answer(k, q, document) for k, q in req.questions.items()))
    except EngineLoading:
        return _unavailable()
    except PromptIntegrityError as e:
        # Should be unreachable; if it fires, refuse rather than send a tampered prompt.
        log.error("prompt integrity violation: %s", e)
        raise HTTPException(422, [{"loc": ["body", "state"], "msg": "input rejected by prompt integrity check",
                                   "type": "integrity_error"}]) from e
    except EngineError as e:
        log.exception("engine error")
        raise HTTPException(500, {"error_type": "engine_error", "message": str(e)}) from e
    return {
        "model": ENGINE.model_name,
        "answers": {k: r[0] for k, r in zip(req.questions, results)},
        "usage": {"input_tokens": sum(r[1] for r in results), "output_tokens": 0},
        "local": {"latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                  "questions": {k: r[2] for k, r in zip(req.questions, results)}},
    }


@app.get("/v1/models", dependencies=[Depends(auth)])
async def models():
    return {"models": [{
        "name": ENGINE.model_name,
        "limits": {"max_options": MAX_OPTIONS, "max_sequence_tokens": max(0, ENGINE.max_model_len - 16),
                   "max_question_tokens": ENGINE.max_model_len // 2, "max_state_tokens": 0},
        "runtime": {"backend": "vllm", "prompt_tps": ENGINE.prompt_tps},
    }]}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    if not STATE["ready"]:
        return JSONResponse(status_code=503, headers={"retry-after": "1"},
                            content={"status": "failed" if "fatal" in STATE else "loading",
                                     "error": STATE.get("fatal")})
    return {"status": "ready", "engine": ENGINE.model_name, "prompt_tps": ENGINE.prompt_tps}
