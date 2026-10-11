"""A decision model on vLLM: one prefill, exact log-probabilities of the option tokens.

vLLM (>= 0.30) accepts `logprob_token_ids`: it returns the log-probability of exactly the
token ids we ask for at the next position (normalized over the FULL vocabulary, raw logits
mode). So for 30 options we get 30 exact numbers in one forward pass: no generation, no
top-k truncation, and `coverage` (mass on valid options) is exact too.

Keys that share a first token are resolved on a token trie: one extra 1-token step on that
branch only, which hits vLLM's prefix cache, so it costs a few tokens, not a new prefill.
"""
import asyncio
import math
import time
from dataclasses import dataclass

import httpx
from tokenizers import Tokenizer

from .prompts import ChatMLBuilder

PARITY_PROBE = "Guvernul a aprobat bugetul. Bucureşti, 3 octombrie — NATO & UE: 5,9% din PIB."
MAX_IDS_PER_CALL = 128  # vLLM's MAX_LOGPROB_TOKEN_IDS


class EngineError(RuntimeError):
    pass


class EngineLoading(EngineError):
    pass


@dataclass
class Scored:
    probabilities: dict[str, float]
    coverage: float
    forward_passes: int


class VllmEngine:
    def __init__(self, base_url: str, api_key: str, tokenizer_path: str, timeout_s: float = 300.0,
                 min_branch_mass: float = 0.01):
        self.c = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=httpx.Timeout(timeout_s, connect=5.0),
                                   headers={"Authorization": f"Bearer {api_key}"})
        self.builder = ChatMLBuilder(Tokenizer.from_file(tokenizer_path))
        self.min_branch_mass = min_branch_mass
        self.model_name = ""
        self.max_model_len = 0
        self.prompt_tps: float | None = None
        self._option_cache: dict[tuple[str, ...], dict[str, list[int]]] = {}

    async def aclose(self) -> None:
        await self.c.aclose()

    async def wait_ready(self, poll_s: float = 2.0) -> None:
        while True:
            try:
                if (await self.c.get("/health")).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(poll_s)
        r = await self.c.get("/v1/models")
        self._check(r)
        card = r.json()["data"][0]
        self.model_name = card["id"]
        self.max_model_len = int(card.get("max_model_len") or 4096)
        await self._check_tokenizer_parity()

    async def _check_tokenizer_parity(self) -> None:
        """Local and server tokenizers MUST agree, or every option id would be wrong."""
        r = await self.c.post("/tokenize", json={"model": self.model_name, "prompt": PARITY_PROBE,
                                                 "add_special_tokens": False})
        self._check(r)
        server = r.json()["tokens"]
        local = self.builder.tok.encode(PARITY_PROBE, add_special_tokens=False).ids
        if server != local:
            raise EngineError(f"tokenizer mismatch between decider and vLLM: {local[:8]} vs {server[:8]}")
        if body := r.json().get("max_model_len"):
            self.max_model_len = int(body)

    @staticmethod
    def _check(r: httpx.Response) -> None:
        if r.status_code == 503:
            raise EngineLoading("vLLM not ready")
        if r.status_code >= 400:
            raise EngineError(f"vLLM {r.status_code}: {r.text[:300]}")

    # ---------------------------------------------------------------- options
    def option_tokens(self, keys: list[str]) -> dict[str, list[int]]:
        ck = tuple(keys)
        if ck in self._option_cache:
            return self._option_cache[ck]
        table = {k: self.builder.option_ids(k) for k in keys}
        for k, t in table.items():
            if not t:
                raise ValueError(f"option {k!r} tokenizes to nothing")
        seqs = sorted(table.items(), key=lambda kv: len(kv[1]))
        for i, (ka, ta) in enumerate(seqs):
            for kb, tb in seqs[i + 1:]:
                if tb[: len(ta)] == ta:
                    raise ValueError(f"option {ka!r} is a token-prefix of {kb!r}; rename one of them")
        if len(self._option_cache) > 256:
            self._option_cache.clear()
        self._option_cache[ck] = table
        return table

    # ---------------------------------------------------------------- scoring
    async def next_token_logprobs(self, prompt: list[int], token_ids: list[int]) -> tuple[dict[int, float], int]:
        if len(token_ids) > MAX_IDS_PER_CALL:
            raise ValueError(f"at most {MAX_IDS_PER_CALL} distinct first tokens per question")
        r = await self.c.post("/v1/completions", json={
            "model": self.model_name,
            "prompt": prompt,                       # token ids: vLLM never tokenizes our text
            "max_tokens": 1,
            "temperature": 0,
            "logprobs": len(token_ids),
            "logprob_token_ids": token_ids,         # exact logprobs for exactly these ids
            "return_tokens_as_token_ids": True,     # keys come back as "token_id:<id>"
        })
        self._check(r)
        body = r.json()
        tops = body["choices"][0]["logprobs"]["top_logprobs"][0] or {}
        out: dict[int, float] = {}
        for key, lp in tops.items():
            if key.startswith("token_id:"):
                out[int(key.split(":", 1)[1])] = float(lp)
        missing = [t for t in token_ids if t not in out]
        if missing:
            raise EngineError(f"vLLM did not return logprobs for ids {missing[:5]} (is logprob_token_ids supported?)")
        return {t: out[t] for t in token_ids}, int(body.get("usage", {}).get("prompt_tokens", len(prompt)))

    async def score(self, prompt: list[int], options: dict[str, list[int]]) -> Scored:
        passes = 0

        async def descend(prefix: list[int], cands: dict[str, list[int]], mass: float, depth: int):
            nonlocal passes
            groups: dict[int, dict[str, list[int]]] = {}
            for k, toks in cands.items():
                groups.setdefault(toks[0], {})[k] = toks[1:]
            lp, _ = await self.next_token_logprobs(prefix, list(groups))
            passes += 1
            seen = sum(math.exp(v) for v in lp.values())
            out: dict[str, float] = {}
            subtasks = []
            for tok, members in groups.items():
                p = mass * math.exp(lp[tok])
                if len(members) == 1 or p < self.min_branch_mass or depth >= 6:
                    for k in members:
                        out[k] = p / len(members)
                else:
                    subtasks.append(descend(prefix + [tok], members, p, depth + 1))
            for sub, _ in await asyncio.gather(*subtasks):
                out.update(sub)
            return out, seen

        raw, coverage = await descend(prompt, options, 1.0, 0)
        total = sum(raw.values()) or 1.0
        return Scored({k: v / total for k, v in raw.items()}, round(coverage, 4), passes)

    async def measure_prefill(self) -> float:
        """Warm-up call, then one timed call on a different document (so the prefix cache
        only covers the shared system part, as in real traffic). Shown in the UI header."""
        opts = [("politics", ""), ("sports", "")]
        first = [t[0] for t in self.option_tokens([k for k, _ in opts]).values()]
        for i, sentence in enumerate(("Parlamentul a adoptat legea bugetului. ",
                                      "Echipa națională a câștigat meciul de aseară. ")):
            ids = self.builder.build(sentence * 120, "Topic?", opts, [])
            t0 = time.perf_counter()
            await self.next_token_logprobs(ids, first)
            if i == 1:
                self.prompt_tps = round(len(ids) / (time.perf_counter() - t0), 1)
        return self.prompt_tps or 0.0
