"""Event coreference: which rows report the same real-world event.

Classic three-step design, run once per job (scope JOB) after `event` and
`entity_resolution` covered every row:

1. Blocking: only rows that report an event are considered, and only pairs that share
   resolved entities (same event type, or a strong entity overlap across types).
   Without blocking this is O(n^2) LLM calls.
2. Pairwise verification: the LLM answers a yes/no question over both reports
   ("same incident, place and time, not just the same topic?"). With `verify: false`
   the entity overlap alone decides (fast, cruder).
3. Clustering: union-find over confirmed pairs; clusters of 2+ rows get an id.
"""
import asyncio
from typing import Any

from ...core.engines import Question
from ...core.modules import Kind, Module, ModuleContext, Scope


class _UnionFind:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


class EventCoreferenceModule(Module):
    name = "event_coreference"
    title = "Same event"
    description = "Groups rows that report the same real-world event (blocking + LLM verification)."
    kind = Kind.CLUSTER
    scope = Scope.JOB
    requires = ("event", "entity_resolution")
    output_columns = ("event_cluster",)
    engine_kinds = ("systemone",)

    def __init__(self, ctx: ModuleContext):
        super().__init__(ctx)
        c = self.cfg
        self.ignore = set(c.get("ignore_event_labels") or ["no_event"])
        self.min_event_confidence = float(c.get("min_event_confidence", 0.3))
        self.min_shared = int(c.get("min_shared_entities", 1))
        self.min_jaccard = float(c.get("min_jaccard", 0.1))
        self.cross_type_jaccard = float(c.get("cross_type_jaccard", 0.34))
        self.max_pairs = int(c.get("max_pairs", 400))
        self.max_entity_rows = int(c.get("max_entity_rows", 50))
        self.verify = bool(c.get("verify", True))
        self.threshold = float(c.get("same_event_threshold", 0.5))
        self.unverified_jaccard = float(c.get("unverified_jaccard", 0.34))
        self.snippet_chars = int(c.get("snippet_chars", 1200))
        self.ignore_entity_labels = set(c.get("ignore_entity_labels") or [])
        self.question = Question("same_event", "noul", str(c["instructions"]).strip(),
                                 {"true": str(c.get("yes", "")), "false": str(c.get("no", ""))})

    # ---------------------------------------------------------------- blocking
    def candidates(self, job) -> list[tuple[float, int, int]]:
        rows: dict[int, tuple[str, set[str]]] = {}
        for i in range(job.total):
            ev, er = job.result("event", i), job.result("entity_resolution", i)
            if not ev or ev["label"] in self.ignore or ev["confidence"] < self.min_event_confidence or not er:
                continue
            ents = {e["id"] for e in er["entities"] if e["label"] not in self.ignore_entity_labels}
            if ents:
                rows[i] = (ev["label"], ents)
        # Inverted index: only pairs that share at least one entity are ever compared.
        by_entity: dict[str, list[int]] = {}
        for i, (_, ents) in rows.items():
            for e in ents:
                by_entity.setdefault(e, []).append(i)
        seen: set[tuple[int, int]] = set()
        out = []
        for members in by_entity.values():
            # An entity in hundreds of event rows (a country, a capital) does not discriminate
            # events, and pairing all its rows is quadratic: it is not used as a blocking key.
            # It still counts in the overlap of pairs found through rarer entities.
            if len(members) > self.max_entity_rows:
                continue
            for x in range(len(members)):
                for y in range(x + 1, len(members)):
                    a, b = members[x], members[y]
                    if (a, b) in seen:
                        continue
                    seen.add((a, b))
                    (la, ea), (lb, eb) = rows[a], rows[b]
                    shared = len(ea & eb)
                    jac = shared / len(ea | eb)
                    same_type = la == lb
                    if shared >= self.min_shared and (
                            (same_type and jac >= self.min_jaccard) or jac >= self.cross_type_jaccard):
                        out.append((jac, a, b))
        out.sort(reverse=True)
        return out[: self.max_pairs]

    # ---------------------------------------------------------------- work
    async def process_job(self, job) -> list[Any]:
        pairs = self.candidates(job)
        if self.verify:
            probs = await asyncio.gather(*(self._same(job, a, b) for _, a, b in pairs))
            links = [(a, b, p) for (_, a, b), p in zip(pairs, probs) if p >= self.threshold]
        else:
            links = [(a, b, j) for j, a, b in pairs if j >= self.unverified_jaccard]

        uf = _UnionFind(job.total)
        for a, b, _ in links:
            uf.union(a, b)
        members: dict[int, list[int]] = {}
        for i in {x for a, b, _ in links for x in (a, b)}:
            members.setdefault(uf.find(i), []).append(i)
        best: dict[int, float] = {}
        for a, b, p in links:
            best[a], best[b] = max(best.get(a, 0), p), max(best.get(b, 0), p)

        results: list[Any] = [None] * job.total
        clusters = sorted((sorted(m) for m in members.values() if len(m) > 1), key=lambda m: m[0])
        for n, rows in enumerate(clusters, start=1):
            for i in rows:
                peers = [j for j in rows if j != i]
                results[i] = {"cluster": f"evt_{n}", "size": len(rows), "peers": peers,
                              "peer_ids": [job.ids[j] for j in peers], "confidence": round(best[i], 4)}
        job.module_state(self.name, dict).update(pairs_checked=len(pairs), links=len(links))
        return results

    async def _same(self, job, a: int, b: int) -> float:
        state = {"report_a": job.texts[a][: self.snippet_chars], "report_b": job.texts[b][: self.snippet_chars]}
        ans = await self.engine.ask(state, self.question, self.engine_options)
        return float(ans["noul"])

    # ---------------------------------------------------------------- presentation
    def to_columns(self, result: Any) -> dict[str, str]:
        return {"event_cluster": result["cluster"] if result else ""}

    def preview(self, result: Any) -> Any:
        return {"cluster": result["cluster"], "size": result["size"]} if result else None

    def matches(self, result: Any, value: str) -> bool:
        return bool(result) and (value == "any" or result["cluster"] == value)

    def summarize(self, job, results: list[Any]) -> dict[str, Any]:
        clusters: dict[str, list[int]] = {}
        for i, r in enumerate(results):
            if r:
                clusters.setdefault(r["cluster"], []).append(i)
        out = []
        for cid, rows in clusters.items():
            ev = job.result("event", rows[0])
            out.append({"id": cid, "size": len(rows), "rows": rows, "ids": [job.ids[i] for i in rows],
                        "event": ev["label"] if ev else None, "title": job.texts[rows[0]][:140]})
        stats = job.state.get(self.name, {})
        return {"clusters": sorted(out, key=lambda c: -c["size"]),
                "pairs_checked": stats.get("pairs_checked", 0), "links": stats.get("links", 0)}
