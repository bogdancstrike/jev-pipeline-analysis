"""The System One engine client: chunking on 422, retries, names-only fallback, batching."""
import json

import httpx
import pytest

from app.core.engines import Question, SystemOneEngine

from .conftest import make_settings

Q = Question("category", "choice", "Topic?", {"sports": "football, goals", "economy": "GDP, inflation"})


def fake(max_state_chars: int, calls: list, fail_first_429: bool = False, q_limit: int = 10_000):
    n = {"calls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/readyz":
            return httpx.Response(200, json={"status": "ready", "engine": "local/fake"})
        if req.url.path == "/v1/models":
            return httpx.Response(200, json={"models": [{"name": "local/fake",
                "limits": {"max_sequence_tokens": 512, "max_question_tokens": 192, "max_options": 255},
                "runtime": {"backend": "vllm"}}]})
        body = json.loads(req.content)
        n["calls"] += 1
        if fail_first_429 and n["calls"] == 1:
            return httpx.Response(429, headers={"retry-after-ms": "10"}, json={"detail": "busy"})
        q = body["questions"]["category"]
        if len(json.dumps(q)) > q_limit:
            return httpx.Response(422, json={"detail": [{"msg": "Question 'category' is about 300 tokens, "
                                                                 "over this model's limit of 192 per question."}]})
        doc = body["state"]["document"]
        calls.append(doc)
        if len(doc) > max_state_chars:
            return httpx.Response(422, json={"detail": [{"msg": "state + question over the 512 sequence limit"}]})
        cat = "sports" if "goal" in doc else "economy"
        probs = {k: (0.8 if k == cat else 0.2) for k in q["criteria"]}
        return httpx.Response(200, json={"answers": {"category": {"choice": cat, "confidence": 0.8,
                                                                  "probabilities": probs}}})
    return httpx.MockTransport(handler)


async def client(transport, **cfg) -> SystemOneEngine:
    c = SystemOneEngine("test", {"url": "http://decision", "max_retries": 3, "chars_per_token": 2.8, **cfg},
                        make_settings())
    c._clients = [httpx.AsyncClient(base_url="http://decision", transport=transport)]
    await c.wait_ready()
    return c


async def choose(c: SystemOneEngine, text: str):
    return (await c.classify([text], Q))[0]


@pytest.mark.asyncio
async def test_long_text_is_split_on_422_and_aggregated():
    calls: list[str] = []
    c = await client(fake(1500, calls), chars_per_token=50.0)  # wrong estimate -> 422 -> halving
    r = await choose(c, "The goal was scored late. " * 400)
    assert r.label == "sports" and r.chunks > 1
    assert max(len(x) for x in calls) > 1500


@pytest.mark.asyncio
async def test_429_is_retried_with_server_hint():
    c = await client(fake(10_000, [], fail_first_429=True))
    assert (await choose(c, "Inflation rose to 5%.")).label == "economy"


@pytest.mark.asyncio
async def test_question_overflow_falls_back_to_names_only_per_question():
    c = await client(fake(10_000, [], q_limit=100))
    assert (await choose(c, "GDP grew.")).label == "economy"
    assert c.names_only == {"category"}


@pytest.mark.asyncio
async def test_batch_endpoint_sends_many_documents_in_one_request():
    from dev.fake_models import decide_batch
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET":
            return httpx.Response(200, json={"status": "ok"})
        calls.append(req.url.path)
        status, out = decide_batch(json.loads(req.content))
        return httpx.Response(status, json=out)

    c = await client(httpx.MockTransport(handler), ready_path="/health", models_path=None,
                     batch={"path": "/v1/systemone/batch", "max_states": 32})
    texts = ["The goal was scored late."] * 20 + ["Inflation and GDP."] * 20
    out = await c.classify(texts, Q)
    assert [r.label for r in out] == ["sports"] * 20 + ["economy"] * 20
    assert calls == ["/v1/systemone/batch", "/v1/systemone/batch"]  # 40 states, 32 per request
