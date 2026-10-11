"""Toxicity: the dominant kind of abusive language, and the probability of any toxicity."""
from typing import Any

from ...core.kits.label import LabelModule


class ToxicityModule(LabelModule):
    name = "toxicity"
    title = "Toxicity"
    description = "Abusive language (insult, hate speech, threat, ...) and an overall toxicity score."
    extra_columns = ("toxicity_score",)

    @property
    def clean_label(self) -> str:
        return str(self.cfg.get("clean_label", "non_toxic"))

    def derive(self, probabilities: dict[str, float]) -> dict[str, Any]:
        score = 1.0 - probabilities.get(self.clean_label, 0.0)
        return {"score": round(score, 4), "toxic": score >= float(self.cfg.get("toxic_above", 0.5))}

    def to_columns(self, result: Any) -> dict[str, str]:
        if not result:
            return {}
        return {**super().to_columns(result), "toxicity_score": f"{result['score']:.4f}"}

    def matches(self, result: Any, value: str) -> bool:
        if value == "toxic":
            return bool(result) and result["toxic"]
        return super().matches(result, value)
