"""Extraction engine: the GLiNER2 service (`extractor/`). Entities, relations, structured
fields and classification from one encoder family, batched, on the GPU.

Model choice is configuration: `model` is an alias the service loaded, or a per-language
route such as {"en": "decide", "*": "decide-multi"} (GLiNER2.5-Decide is English-only;
the service detects each text's language and sends it to the right checkpoint).
Modules can override it per task (`engine_options: {model: extract-multi}`).
"""
import asyncio
from typing import Any

import httpx

from ..config import Settings
from .base import Classification, Engine, EngineError, Question, read_secret

_OPTION_KEYS = ("model", "threshold", "chunk_size", "chunk_overlap", "batch_size")


class Gliner2Engine(Engine):
    kind = "gliner2"

    def __init__(self, name: str, cfg: dict[str, Any], settings: Settings):
        super().__init__(name, cfg, settings)
        key = read_secret(settings, cfg.get("api_key_secret"))
        self._c = httpx.AsyncClient(base_url=str(cfg["url"]).rstrip("/"),
                                    headers={"Authorization": f"Bearer {key}"} if key else {},
                                    timeout=httpx.Timeout(float(cfg.get("timeout_s", 600)), connect=5.0))
        self.defaults = {k: cfg[k] for k in _OPTION_KEYS if k in cfg}
        self.max_texts = int(cfg.get("max_texts_per_request", 32))
        self._sem = asyncio.Semaphore(int(cfg.get("concurrency", 2)))

    async def aclose(self) -> None:
        await self._c.aclose()

    async def wait_ready(self, poll_s: float = 2.0) -> None:
        while True:
            try:
                r = await self._c.get("/readyz")
                if r.status_code == 200:
                    body = r.json()
                    self.info = {"model": ", ".join(f"{a}={m}" for a, m in body.get("models", {}).items()),
                                 "device": body.get("gpu") or body.get("device"),
                                 "vram_reserved_mb": body.get("vram_reserved_mb")}
                    self.ready = True
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(poll_s)

    async def extract(self, task: str, texts: list[str], spec: Any, options: dict[str, Any] | None = None
                      ) -> list[Any]:
        opts = {**self.defaults, **{k: v for k, v in (options or {}).items() if k in _OPTION_KEYS}}
        groups = [texts[i:i + self.max_texts] for i in range(0, len(texts), self.max_texts)]
        parts = await asyncio.gather(*(self._post({"task": task, "texts": g, "spec": spec, **opts}) for g in groups))
        return [r for p in parts for r in p]

    async def _post(self, body: dict) -> list[Any]:
        for attempt in range(6):
            try:
                async with self._sem:
                    t0 = self.metrics.begin()
                    try:
                        r = await self._c.post("/v1/extract", json=body)
                    except BaseException:
                        self.metrics.end(t0, ok=False)
                        raise
                    self.metrics.end(t0, ok=r.status_code == 200, items=len(body["texts"]))
                if r.status_code == 200:
                    return r.json()["results"]
                if r.status_code < 500 and r.status_code != 429:
                    raise EngineError(f"engine {self.name}: {r.status_code} {r.text[:300]}")
            except httpx.TransportError:
                pass
            self.metrics.retries += 1
            await asyncio.sleep(0.5 * 2**attempt)
        raise EngineError(f"engine {self.name}: unavailable")

    async def classify(self, texts: list[str], q: Question, options: dict[str, Any] | None = None
                       ) -> list[Classification | None]:
        """A choice as GLiNER2 classification. Labels carry their descriptions (the model reads
        them); the instruction is the task name's prompt. Empty texts get None."""
        idx = [i for i, t in enumerate(texts) if t.strip()]
        spec = {q.key: {"labels": {k: (v or k.replace("_", " ")) for k, v in q.criteria.items()}}}
        out: list[Classification | None] = [None] * len(texts)
        if not idx:
            return out
        results = await self.extract("classify", [texts[i] for i in idx], spec, options)
        for i, res in zip(idx, results):
            r = (res or {}).get(q.key)
            if isinstance(r, dict) and "label" in r:
                conf = float(r.get("confidence", 0.0))
                out[i] = Classification(str(r["label"]), round(conf, 4), {str(r["label"]): conf})
        return out
