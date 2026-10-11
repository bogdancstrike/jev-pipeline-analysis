"""Sentiment: the overall tone of the document, plus a signed score in [-1, 1]."""
from typing import Any

from ...core.kits.label import LabelModule


class SentimentModule(LabelModule):
    name = "sentiment"
    title = "Sentiment"
    description = "Overall tone of the text, with a score from -1 (negative) to +1 (positive)."
    extra_columns = ("sentiment_score",)

    def derive(self, probabilities: dict[str, float]) -> dict[str, Any]:
        score = probabilities.get("positive", 0.0) - probabilities.get("negative", 0.0)
        return {"score": round(score, 4)}

    def to_columns(self, result: Any) -> dict[str, str]:
        if not result:
            return {}
        return {**super().to_columns(result), "sentiment_score": f"{result['score']:.4f}"}
