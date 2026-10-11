"""Relations between entities, with two strategies picked by the configured engine:

* `gliner2` engine (default, GLiNER2.5): one batched relation-extraction pass per batch of
  rows. The model returns directed (head, relation, tail) spans; heads and tails are then
  mapped onto resolved entity ids by span overlap, so relations link to `entity_resolution`.
* `systemone` engine (Laya, Kev, the LLM decider): entity pairs whose mentions share a
  sentence are candidates, nearest first, capped at `max_pairs`; each pair is one closed
  question over that sentence, with `no_relation` as an option so nothing is invented.
  Direction is fixed before asking ("HEAD <relation> TAIL"): a person before an
  organization, a place last, otherwise text order.
"""
import asyncio
import json
import re
from typing import Any

from ...core.engines import Question
from ...core.modules import Kind, Module, ModuleContext

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n+")


def sentences(text: str) -> list[tuple[int, int]]:
    out, start = [], 0
    for m in _SENTENCE_END.finditer(text):
        out.append((start, m.start()))
        start = m.end()
    out.append((start, len(text)))
    return [(a, b) for a, b in out if b > a]


class RelationsModule(Module):
    name = "relations"
    title = "Relations"
    description = "How co-occurring entities relate (member of, leader of, located in, opposes, ...)."
    kind = Kind.RELATIONS
    requires = ("entity_resolution",)
    output_columns = ("relations",)
    engine_kinds = ("gliner2", "systemone")
    default_concurrency = 2
    default_batch_size = 8

    def __init__(self, ctx: ModuleContext):
        super().__init__(ctx)
        self.labels = {str(k): str(v or "") for k, v in (self.cfg.get("labels") or {}).items()}
        self.none_label = str(self.cfg.get("none_label", "no_relation"))
        if self.none_label not in self.labels:
            raise ValueError(f"relations: `{self.none_label}` must be one of the labels")
        self.instructions = str(self.cfg["instructions"]).strip()
        self.entity_labels = set(self.cfg.get("entity_labels") or [])
        self.first_labels = set(self.cfg.get("head_first_labels") or ["person"])
        self.last_labels = set(self.cfg.get("tail_last_labels") or [])
        self.skip_within = set(self.cfg.get("skip_pairs_within") or [])
        self.max_pairs = int(self.cfg.get("max_pairs", 6))
        self.min_confidence = float(self.cfg.get("min_confidence", 0.5))
        self.context_chars = int(self.cfg.get("context_chars", 1200))
        self.max_relations = int(self.cfg.get("max_relations", 12))

    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "labels": {k: v for k, v in self.labels.items() if k != self.none_label}}

    # ---------------------------------------------------------------- candidates
    def candidates(self, text: str, entities: list[dict]) -> list[tuple[dict, dict, str]]:
        """-> [(head, tail, context sentence)] nearest-first, at most `max_pairs`."""
        bounds = sentences(text)

        def sentence_of(pos: int) -> int:
            return next((k for k, (a, b) in enumerate(bounds) if a <= pos < b), len(bounds) - 1)

        ents = [e for e in entities if not self.entity_labels or e["label"] in self.entity_labels]
        where = {e["id"]: {sentence_of(s[0]): s[0] for s in reversed(e["spans"])} for e in ents}
        scored = []
        for x in range(len(ents)):
            for y in range(x + 1, len(ents)):
                a, b = ents[x], ents[y]
                if a["label"] in self.skip_within and b["label"] in self.skip_within:
                    continue
                shared = set(where[a["id"]]) & set(where[b["id"]])
                if not shared:
                    continue
                k = min(shared, key=lambda s: abs(where[a["id"]][s] - where[b["id"]][s]))
                dist = abs(where[a["id"]][k] - where[b["id"]][k])
                scored.append((dist, *self._direct(a, b), k))
        scored.sort(key=lambda t: t[0])
        out = []
        for _, head, tail, k in scored[: self.max_pairs]:
            a, b = bounds[k]
            out.append((head, tail, text[a:b][: self.context_chars]))
        return out

    def _direct(self, a: dict, b: dict) -> tuple[dict, dict]:
        if b["label"] in self.first_labels and a["label"] not in self.first_labels:
            return b, a
        if a["label"] in self.last_labels and b["label"] not in self.last_labels:
            return b, a
        return a, b

    # ---------------------------------------------------------------- work
    async def process_rows(self, job, idxs: list[int]) -> list[Any]:
        if self.engine.kind == "gliner2":
            return await self._extract_rows(job, idxs)
        return list(await asyncio.gather(*(self._row(job, i) for i in idxs)))

    # ---------------------------------------------------------------- gliner2 strategy
    async def _extract_rows(self, job, idxs: list[int]) -> list[Any]:
        spec = {k: (v or k.replace("_", " ")) for k, v in self.labels.items() if k != self.none_label}
        live = [i for i in idxs if job.texts[i].strip()]
        found = dict(zip(live, await self.engine.extract("relations", [job.texts[i] for i in live], spec,
                                                         self.engine_options))) if live else {}
        out = []
        for i in idxs:
            er = job.result("entity_resolution", i)
            ents = er["entities"] if er else []
            rels, seen = [], set()
            for r in found.get(i, []):
                if r["score"] < self.min_confidence:
                    continue
                head, tail = self._entity_at(ents, r["head"]), self._entity_at(ents, r["tail"])
                h_name = head["name"] if head else r["head"]["text"]
                t_name = tail["name"] if tail else r["tail"]["text"]
                key = (h_name.casefold(), r["relation"], t_name.casefold())
                if key in seen or h_name.casefold() == t_name.casefold():
                    continue
                seen.add(key)
                rels.append({"head": h_name, "head_id": head["id"] if head else None,
                             "head_label": head["label"] if head else None, "relation": r["relation"],
                             "tail": t_name, "tail_id": tail["id"] if tail else None,
                             "tail_label": tail["label"] if tail else None, "confidence": r["score"],
                             "evidence": self._evidence(job.texts[i], r)})
                if len(rels) >= self.max_relations:
                    break
            out.append({"relations": rels, "pairs_checked": len(found.get(i, []))})
        return out

    @staticmethod
    def _entity_at(entities: list[dict], span: dict) -> dict | None:
        """The resolved entity one of whose mentions overlaps this span, if any."""
        s, e = span.get("start"), span.get("end")
        if s is None or e is None:
            return None
        for ent in entities:
            if any(a < e and s < b for a, b in ent["spans"]):
                return ent
        return None

    def _evidence(self, text: str, r: dict) -> str:
        pos = [p for p in (r["head"].get("start"), r["tail"].get("start")) if p is not None]
        if not pos:
            return ""
        bounds = sentences(text)
        k = next((k for k, (a, b) in enumerate(bounds) if a <= min(pos) < b), 0)
        a, b = bounds[k]
        return text[a:b][: self.context_chars]

    # ---------------------------------------------------------------- systemone strategy

    async def _row(self, job, i: int) -> dict[str, Any]:
        er = job.result("entity_resolution", i)
        pairs = self.candidates(job.texts[i], er["entities"] if er else [])
        answers = await asyncio.gather(*(self._ask(h, t, ctx) for h, t, ctx in pairs))
        rels = [r for r in answers if r]
        return {"relations": rels, "pairs_checked": len(pairs)}

    async def _ask(self, head: dict, tail: dict, context: str) -> dict[str, Any] | None:
        q = Question("relation", "choice", self.instructions.format(
            head=head["name"], head_label=head["label"], tail=tail["name"], tail_label=tail["label"]), self.labels)
        r = (await self.engine.classify([context], q, self.engine_options))[0]
        if r is None or r.label == self.none_label or r.confidence < self.min_confidence:
            return None
        return {"head": head["name"], "head_id": head["id"], "head_label": head["label"],
                "relation": r.label, "tail": tail["name"], "tail_id": tail["id"],
                "tail_label": tail["label"], "confidence": r.confidence, "evidence": context}

    async def finalize(self, job) -> None:
        """Entity ids may have merged after a row was processed: point at the survivors."""
        reg = job.state.get("entity_resolution")
        if reg is None:
            return
        for r in job.results[self.name]:
            for rel in (r or {}).get("relations", []):
                for side in ("head", "tail"):
                    if (c := reg.canonical(rel[f"{side}_id"])) is not None:
                        rel[f"{side}_id"], rel[side] = c

    # ---------------------------------------------------------------- presentation
    def to_columns(self, result: Any) -> dict[str, str]:
        triples = [[r["head"], r["relation"], r["tail"]] for r in (result or {}).get("relations", [])]
        return {"relations": json.dumps(triples, ensure_ascii=False)}

    def preview(self, result: Any) -> Any:
        if not result:
            return None
        return [{k: r[k] for k in ("head", "relation", "tail", "confidence")} for r in result["relations"]]

    def matches(self, result: Any, value: str) -> bool:
        return bool(result) and any(r["relation"] == value for r in result["relations"])

    def summarize(self, job, results: list[Any]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for r in results:
            for rel in (r or {}).get("relations", []):
                counts[rel["relation"]] = counts.get(rel["relation"], 0) + 1
        return {"counts": dict(sorted(counts.items(), key=lambda kv: -kv[1]))}
