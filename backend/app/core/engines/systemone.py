"""Decision engines that speak the System One protocol (POST /v1/systemone): Laya, Kev, the
vLLM-backed decider, or the hosted Jev API. One client, configured per engine.

  POST /v1/systemone {model, state, questions:{key:{type, instructions, criteria}}, ...extras}
  -> answers[key] = choice: {choice, confidence, probabilities} | noul: {noul: P(yes)}
  POST /v1/systemone/batch {states:[...], questions, ...}   (Laya) -> {results:[{answers}...]}
  422 = over the window, 429/503 + retry-after = busy/loading.

This client owns transport, retries, readiness, token budgets and long-text chunking
(engines differ: the decider answers 422 over its window, Laya silently truncates, so texts
are pre-split to the configured budget and per-chunk answers aggregated).
"""
import asyncio
import itertools
import json
import logging
import random
from typing import Any

import httpx

from ..chunking import aggregate, halve, split_text
from ..config import Settings
from .base import Classification, Engine, EngineError, Question, read_secret

log = logging.getLogger("engine.systemone")

MIN_CHUNK_CHARS = 200


class StateTooLong(EngineError):
    pass


class QuestionTooLong(EngineError):
    pass


class SystemOneEngine(Engine):
    kind = "systemone"

    def __init__(self, name: str, cfg: dict[str, Any], settings: Settings):
        super().__init__(name, cfg, settings)
        urls = cfg.get("urls") or [cfg["url"]]
        key = read_secret(settings, cfg.get("api_key_secret"))
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        self.concurrency = int(cfg.get("concurrency", 6))
        self._clients = [
            httpx.AsyncClient(base_url=str(u).rstrip("/"), headers=headers,
                              timeout=httpx.Timeout(float(cfg.get("timeout_s", 300)), connect=5.0),
                              limits=httpx.Limits(max_connections=self.concurrency * 2,
                                                  max_keepalive_connections=self.concurrency))
            for u in urls
        ]
        self._rr = itertools.cycle(range(len(self._clients)))
        self._sem = asyncio.Semaphore(self.concurrency * len(self._clients))
        lim = cfg.get("limits") or {}
        self.max_sequence_tokens = int(lim.get("max_sequence_tokens", 4096))
        self.max_question_tokens = int(lim.get("max_question_tokens", 1024))
        self.max_state_tokens = int(lim.get("max_state_tokens", 0))
        self.chars_per_token = float(cfg.get("chars_per_token", 3.5))
        self.lead_chunk_weight = float(cfg.get("lead_chunk_weight", 1.5))
        self.max_retries = int(cfg.get("max_retries", 8))
        self.ready_path = cfg.get("ready_path", "/readyz")
        self.models_path = cfg.get("models_path", "/v1/models")
        self.request_extra: dict[str, Any] = dict(cfg.get("request") or {})
        batch = cfg.get("batch") or {}
        self.batch_path: str | None = batch.get("path")
        self.batch_max_states = int(batch.get("max_states", 32))
        self.model = str(cfg.get("model", ""))
        self.names_only: set[str] = set()  # question keys whose descriptions overflowed

    async def aclose(self) -> None:
        await asyncio.gather(*(c.aclose() for c in self._clients))

    # ------------------------------------------------------------------ discovery
    async def wait_ready(self, poll_s: float = 2.0) -> None:
        while True:
            try:
                for c in self._clients:
                    r = await c.get(self.ready_path)
                    if r.status_code != 200:
                        raise EngineError(f"{c.base_url} not ready: {r.status_code} {r.text[:120]}")
                    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                    self.model = self.model or str(body.get("engine") or "")
                    if "prompt_tps" in body:
                        self.info["prompt_tps"] = body["prompt_tps"]
                    if "loaded" in body:
                        self.info["loaded"] = body["loaded"]
                    if "device" in body:
                        self.info["device"] = body["device"]
                    self._check_degraded(body)
                if self.models_path:
                    await self._discover()
                self.info.update(model=self.model or self.name, max_sequence_tokens=self.max_sequence_tokens,
                                 replicas=len(self._clients))
                self.ready = True
                log.info("engine %s ready: %s", self.name, self.info)
                return
            except (httpx.HTTPError, EngineError, ValueError) as e:
                log.info("waiting for engine %s: %s", self.name, e)
                await asyncio.sleep(poll_s)

    def _check_degraded(self, body: dict) -> None:
        """Laya moves a checkpoint to the CPU after a CUDA OOM and keeps serving, ~30x slower.
        Surface that, or the only symptom is a pipeline that crawls."""
        cpu = [n for n, d in (body.get("checkpoint_devices") or {}).items() if d == "cpu"]
        self.info["degraded"] = (f"{', '.join(cpu)} running on the CPU (GPU memory ran out): restart the "
                                 f"{self.name} service" if cpu else None)

    async def refresh(self) -> None:
        """Re-read the readiness endpoint (device state can change while running)."""
        try:
            r = await self._clients[0].get(self.ready_path)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                self._check_degraded(r.json())
        except httpx.HTTPError:
            pass

    async def _discover(self) -> None:
        """Read limits the server publishes (the decider does); config values win if set."""
        r = await self._clients[0].get(self.models_path)
        if r.status_code != 200:
            return
        models = r.json().get("models", [])
        entry = next((m for m in models if m.get("name") == self.model), models[0] if models else {})
        lim, rt = entry.get("limits", {}), entry.get("runtime", {})
        cfg_lim = self.cfg.get("limits") or {}
        if "max_sequence_tokens" not in cfg_lim and lim.get("max_sequence_tokens"):
            self.max_sequence_tokens = int(lim["max_sequence_tokens"])
        if "max_question_tokens" not in cfg_lim and lim.get("max_question_tokens"):
            self.max_question_tokens = int(lim["max_question_tokens"])
        self.model = self.model or entry.get("name", "")
        if rt.get("prompt_tps") is not None:
            self.info["prompt_tps"] = rt["prompt_tps"]
        if rt.get("backend"):
            self.info["device"] = rt["backend"]

    # ------------------------------------------------------------------ budgets
    def state_char_budget(self, q: Question) -> int:
        payload = q.payload(q.key in self.names_only)
        q_tokens_est = len(json.dumps(payload, ensure_ascii=False)) / 2.0  # pessimistic
        reserve = min(self.max_question_tokens, int(q_tokens_est)) + 24  # + envelope
        tokens = self.max_sequence_tokens - reserve
        if self.max_state_tokens:
            tokens = min(tokens, self.max_state_tokens)
        return max(MIN_CHUNK_CHARS, int(tokens * self.chars_per_token))

    # ------------------------------------------------------------------ transport
    def _body(self, q: Question, options: dict[str, Any] | None) -> dict[str, Any]:
        body: dict[str, Any] = {**self.request_extra, **(options or {}),
                                "questions": {q.key: q.payload(q.key in self.names_only)}}
        if self.model and "model" not in body:
            body["model"] = self.model
        return body

    async def _send(self, path: str, payload: dict) -> dict:
        attempt = 0
        while True:
            client = self._clients[next(self._rr)]
            items = len(payload.get("states") or [0])
            try:
                async with self._sem:
                    t0 = self.metrics.begin()
                    try:
                        r = await client.post(path, json=payload)
                    except BaseException:
                        self.metrics.end(t0, ok=False)
                        raise
                    self.metrics.end(t0, ok=r.status_code == 200, items=items)
            except httpx.TransportError as e:
                r, err = None, e
            else:
                err = None
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 422:
                    self._raise_422(r)
                if r.status_code in (401, 403):
                    raise EngineError(f"engine {self.name}: auth rejected ({r.status_code})")
                retryable = (r.status_code == 429 or (r.status_code == 503 and "retry-after" in r.headers)
                             or (r.status_code >= 500 and r.status_code != 503))
                if not retryable:
                    raise EngineError(f"engine {self.name}: {r.status_code} {r.text[:300]}")
            attempt += 1
            self.metrics.retries += 1
            if attempt > self.max_retries:
                raise EngineError(f"engine {self.name}: giving up after {attempt} attempts: {err or r.status_code}")
            await asyncio.sleep(self._backoff(r, attempt))

    @staticmethod
    def _backoff(r: httpx.Response | None, attempt: int) -> float:
        # Honour the server's hint; blind exponential backoff makes an overloaded engine worse.
        if r is not None:
            if ms := r.headers.get("retry-after-ms"):
                return float(ms) / 1000 + random.uniform(0, 0.05)
            if s := r.headers.get("retry-after"):
                return float(s) + random.uniform(0, 0.25)
        return min(10.0, 0.25 * 2**attempt) + random.uniform(0, 0.1)

    @staticmethod
    def _raise_422(r: httpx.Response) -> None:
        rid = r.headers.get("x-request-id", "?")
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = r.text
        msgs = " | ".join(d.get("msg", "") for d in detail) if isinstance(detail, list) else str(detail)
        low = msgs.lower()
        if "per question" in low:
            raise QuestionTooLong(f"[{rid}] {msgs}")
        if any(w in low for w in ("state", "sequence", "token")):
            raise StateTooLong(f"[{rid}] {msgs}")
        raise EngineError(f"422 [{rid}] {msgs}")

    # ------------------------------------------------------------------ ports
    async def ask(self, state: dict, q: Question, options: dict[str, Any] | None = None) -> dict:
        """One call, no chunking: for small structured states (pairs, snippets)."""
        try:
            return (await self._send("/v1/systemone", {**self._body(q, options), "state": state}))["answers"][q.key]
        except QuestionTooLong:
            if q.key in self.names_only or q.type != "choice":
                raise
            log.warning("engine %s: question %r overflows the budget; using option names only", self.name, q.key)
            self.names_only.add(q.key)
            return await self.ask(state, q, options)

    async def classify(self, texts: list[str], q: Question, options: dict[str, Any] | None = None
                       ) -> list[Classification | None]:
        """A choice per text, any length: split to the budget, ask per chunk, aggregate."""
        budget = self.state_char_budget(q)
        chunked = [split_text(t, budget) for t in texts]
        flat = [(i, k, c) for i, chunks in enumerate(chunked) for k, c in enumerate(chunks)]
        if self.batch_path and len(flat) > 1:
            probs = await self._batch_probs([c for _, _, c in flat], q, options)
            parts: dict[int, list[tuple[float, dict]]] = {}
            for (i, k, c), p in zip(flat, probs):
                parts.setdefault(i, []).append((len(c) * (self.lead_chunk_weight if k == 0 else 1.0), p))
        else:
            per_text = await asyncio.gather(*(self._weighted(chunks, q, options) for chunks in chunked))
            parts = {i: w for i, w in enumerate(per_text) if w}
        out: list[Classification | None] = []
        for i in range(len(texts)):
            if not parts.get(i):
                out.append(None)
                continue
            label, conf, dist = aggregate(parts[i])
            out.append(Classification(label, round(conf, 4), dist, chunks=len(parts[i])))
        return out

    async def _batch_probs(self, chunks: list[str], q: Question, options: dict[str, Any] | None) -> list[dict]:
        body = self._body(q, options)
        size = self.batch_max_states

        async def one(group: list[str]) -> list[dict]:
            res = await self._send(self.batch_path, {**body, "states": [{"document": c} for c in group]})
            return [r["answers"][q.key]["probabilities"] for r in res["results"]]

        groups = await asyncio.gather(*(one(chunks[i:i + size]) for i in range(0, len(chunks), size)))
        return [p for g in groups for p in g]

    async def _weighted(self, chunks: list[str], q: Question, options) -> list[tuple[float, dict]]:
        results = await asyncio.gather(*(self._chunk(c, q, options, 0) for c in chunks))
        out = []
        for k, parts in enumerate(results):
            for part_len, probs in parts:
                out.append((part_len * (self.lead_chunk_weight if k == 0 else 1.0), probs))
        return out

    async def _chunk(self, chunk: str, q: Question, options, depth: int) -> list[tuple[int, dict[str, float]]]:
        # Untrusted text goes in its own labeled field, never mixed with our instructions.
        try:
            ans = await self.ask({"document": chunk}, q, options)
            return [(len(chunk), ans["probabilities"])]
        except StateTooLong:
            if depth >= 6 or len(chunk) < MIN_CHUNK_CHARS:
                raise
            a, b = halve(chunk)
            ra, rb = await asyncio.gather(self._chunk(a, q, options, depth + 1), self._chunk(b, q, options, depth + 1))
            return ra + rb
