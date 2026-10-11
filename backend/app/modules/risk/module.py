"""Risk level: how much harm or urgency the document signals, on an ordered scale.

Labels are ordered from lowest to highest risk in the config; `score` is the expected level
on [0, 1] (0 = first label, 1 = last), so rows can be sorted by risk, not just bucketed.
"""
from typing import Any

from ...core.kits.label import LabelModule


class RiskModule(LabelModule):
    name = "risk"
    title = "Risk"
    description = "Risk level the text signals (none to critical), with an expected-risk score."
    extra_columns = ("risk_score",)

    def derive(self, probabilities: dict[str, float]) -> dict[str, Any]:
        levels = list(self.labels)
        if len(levels) < 2 or not probabilities:
            return {}
        total = sum(probabilities.get(k, 0.0) for k in levels) or 1.0
        expected = sum(i * probabilities.get(k, 0.0) for i, k in enumerate(levels)) / total
        return {"score": round(expected / (len(levels) - 1), 4)}

    def to_columns(self, result: Any) -> dict[str, str]:
        if not result:
            return {}
        cols = super().to_columns(result)
        if "score" in result:
            cols["risk_score"] = f"{result['score']:.4f}"
        return cols
