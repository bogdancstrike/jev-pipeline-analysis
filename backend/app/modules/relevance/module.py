"""Relevance: does this document matter for the analyst brief in the config?

The brief is the instruction, so retargeting the feed (cyber, elections, energy, ...) is a
config edit. `score` = P(relevant), so rows can be ranked as well as filtered.
"""
from typing import Any

from ...core.kits.label import LabelModule


class RelevanceModule(LabelModule):
    name = "relevance"
    title = "Relevance"
    description = "Whether the text matters for the configured analyst brief, with a ranking score."
    extra_columns = ("relevance_score",)

    def derive(self, probabilities: dict[str, float]) -> dict[str, Any]:
        positive = str(self.cfg.get("positive_label", "relevant"))
        return {"score": round(probabilities.get(positive, 0.0), 4)} if positive in probabilities else {}

    def to_columns(self, result: Any) -> dict[str, str]:
        if not result:
            return {}
        cols = super().to_columns(result)
        if "score" in result:
            cols["relevance_score"] = f"{result['score']:.4f}"
        return cols
