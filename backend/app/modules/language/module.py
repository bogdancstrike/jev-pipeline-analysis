"""Language identification, locally on the CPU (py3langid: langid.py's model, BSD).

No GPU and no service call: ~thousands of short texts per second. The candidate set is
restricted to `languages` in the config, which makes it markedly more accurate than
open-set detection on short, noisy OSINT text.
"""
import asyncio
from typing import Any

from py3langid.langid import MODEL_FILE, LanguageIdentifier

from ...core.modules import Kind, Module, ModuleContext

_SAMPLE_CHARS = 2000  # the first 2k chars decide; longer input only costs time


class LanguageModule(Module):
    name = "language"
    title = "Language"
    description = "Language of the text (ISO 639-1), detected locally without the GPU."
    kind = Kind.LABEL
    output_columns = ("language", "language_confidence")
    default_batch_size = 64
    default_concurrency = 1

    def __init__(self, ctx: ModuleContext):
        super().__init__(ctx)
        self.names: dict[str, str] = {str(k): str(v) for k, v in (self.cfg.get("languages") or {}).items()}
        self.review_below = float(self.cfg.get("review_below", 0.8))
        self.identifier = LanguageIdentifier.from_pickled_model(MODEL_FILE, norm_probs=True)
        if self.names:
            self.identifier.set_languages(list(self.names))

    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "labels": self.names, "review_below": self.review_below}

    async def process_rows(self, job, idxs: list[int]) -> list[Any]:
        texts = [job.texts[i][:_SAMPLE_CHARS] for i in idxs]
        return await asyncio.to_thread(lambda: [self._detect(t) for t in texts])

    def _detect(self, text: str) -> dict[str, Any] | None:
        if not text.strip():
            return None
        ranked = self.identifier.rank(text)[:3]
        label, conf = ranked[0]
        return {"label": label, "confidence": round(float(conf), 4),
                "top": [[k, round(float(p), 4)] for k, p in ranked]}

    def to_columns(self, result: Any) -> dict[str, str]:
        if not result:
            return {}
        return {"language": result["label"], "language_confidence": f"{result['confidence']:.4f}"}

    def preview(self, result: Any) -> Any:
        return {"label": result["label"], "confidence": result["confidence"]} if result else None

    def needs_review(self, result: Any) -> bool:
        return bool(result) and result["confidence"] < self.review_below

    def matches(self, result: Any, value: str) -> bool:
        return bool(result) and result["label"] == value

    def summarize(self, job, results: list[Any]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for r in results:
            if r:
                counts[r["label"]] = counts.get(r["label"], 0) + 1
        return {"counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
                "needs_review": sum(1 for r in results if self.needs_review(r))}
