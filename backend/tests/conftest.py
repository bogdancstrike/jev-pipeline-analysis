"""Shared fixtures: real modules + real config, fake engines via httpx.MockTransport."""
import json
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.core.engines import Gliner2Engine, SystemOneEngine  # noqa: F401  (re-exported for tests)
from app.core.platform import Platform
from app.modules import CATALOG
from dev.fake_models import decide, decide_batch, extract

ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "config"
SAMPLES = ROOT / "samples"
SAMPLE = SAMPLES / "curated.csv"  # 50 short, hand-written edge cases


def make_settings(**kw) -> Settings:
    base = dict(modules_dir=str(CONFIG / "modules"), engines_path=str(CONFIG / "engines.yaml"),
                samples_dir=str(SAMPLES))
    return Settings(**{**base, **kw})


def systemone_transport(calls: list | None = None) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET":
            return httpx.Response(200, json={"status": "ok"}) if req.url.path in ("/health", "/readyz") \
                else httpx.Response(404, json={"detail": "not found"})
        body = json.loads(req.content)
        if calls is not None:
            calls.append(body)
        status, out = decide_batch(body) if req.url.path.endswith("/batch") else decide(body)
        return httpx.Response(status, json=out, headers={"x-request-id": "req_test"})
    return httpx.MockTransport(handler)


def extractor_transport() -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/readyz":
            return httpx.Response(200, json={"status": "ready", "models": {"fake": "fake"}, "device": "cpu"})
        return httpx.Response(200, json=extract(json.loads(req.content)))
    return httpx.MockTransport(handler)


def build_platform(settings: Settings | None = None, calls: list | None = None) -> Platform:
    p = Platform.build(settings or make_settings(), CATALOG)
    for e in p.engines.used:
        if e.kind == "systemone":
            e._clients = [httpx.AsyncClient(base_url="http://engine", transport=systemone_transport(calls))]
        else:
            e._c = httpx.AsyncClient(base_url="http://extractor", transport=extractor_transport())
    return p


@pytest.fixture
def platform() -> Platform:
    return build_platform()
