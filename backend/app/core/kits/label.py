"""Building block for "pick one label for this document" modules.

A module built on it is mostly configuration: `engine`, `instructions` and `labels` in its
YAML file. It runs on any engine (the `classify` port): a System One decision model (Laya,
Kev, the vLLM decider) or GLiNER2 classification. Subclasses add meaning on top (a
sentiment score, a list of propaganda techniques) by overriding `derive`, and extra CSV
columns via `extra_columns` + `to_columns`.
"""
from typing import Any, ClassVar

from ..engines import Question
from ..modules import Kind, Module, ModuleContext


class LabelModule(Module):
    kind = Kind.LABEL
    engine_kinds = ("systemone", "gliner2")
    default_batch_size = 16
    default_concurrency = 2
    extra_columns: ClassVar[tuple[str, ...]] = ()

    def __init__(self, ctx: ModuleContext):
        super().__init__(ctx)
        labels = {str(k): str(v or "") for k, v in (self.cfg.get("labels") or {}).items()}
        if len(labels) < 2:
            raise ValueError(f"{self.name}: config needs at least 2 labels")
        instructions = str(self.cfg.get("instructions") or "").strip()
        if not instructions:
            raise ValueError(f"{self.name}: config needs `instructions`")
        self.labels = labels
        self.question = Question(self.name, "choice", instructions, labels)
        self.review_below = float(self.cfg.get("review_below", 0.5))
        self.top_k = int(self.cfg.get("top_k", 5))
        self.max_chars = int(self.cfg.get("max_chars", 0))  # 0 = whole text
        self.output_columns = (self.name, f"{self.name}_confidence", *self.extra_columns)

    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "labels": self.labels, "review_below": self.review_below}

    # ---------------------------------------------------------------- work
    async def process_rows(self, job, idxs: list[int]) -> list[Any]:
        """One engine call for the whole batch (engines batch or parallelize inside)."""
        texts = [job.texts[i][: self.max_chars] if self.max_chars else job.texts[i] for i in idxs]
        live = [k for k, t in enumerate(texts) if t.strip()]
        out: list[Any] = [None] * len(texts)
        if not live:
            return out
        results = await self.engine.classify([texts[k] for k in live], self.question, self.engine_options)
        for k, r in zip(live, results):
            if r is None:
                continue
            top = sorted(r.probabilities.items(), key=lambda kv: -kv[1])[: self.top_k]
            out[k] = {"label": r.label, "confidence": r.confidence,
                      "top": [[lbl, round(p, 4)] for lbl, p in top], **self.derive(r.probabilities)}
        return out

    def derive(self, probabilities: dict[str, float]) -> dict[str, Any]:
        """Extra fields computed from the full distribution (it is not stored)."""
        return {}

    # ---------------------------------------------------------------- presentation
    def to_columns(self, result: Any) -> dict[str, str]:
        if not result:
            return {}
        return {self.name: result["label"], f"{self.name}_confidence": f"{result['confidence']:.4f}"}

    def preview(self, result: Any) -> Any:
        if not result:
            return None
        return {k: v for k, v in result.items() if k != "top"}

    def needs_review(self, result: Any) -> bool:
        return bool(result) and result["confidence"] < self.review_below

    def matches(self, result: Any, value: str) -> bool:
        return bool(result) and result["label"] == value

    def summarize(self, job, results: list[Any]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        review = 0
        for r in results:
            if r:
                counts[r["label"]] = counts.get(r["label"], 0) + 1
                review += r["confidence"] < self.review_below
        return {"counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])), "needs_review": review}
