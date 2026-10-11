"""Propaganda techniques (SemEval-2020 Task 11 inventory).

The engine answers one choice, so the label is the *dominant* technique. Every technique
whose probability clears `min_probability` is reported too, which approximates the
multi-label nature of the task at no extra cost.
"""
from typing import Any

from ...core.kits.label import LabelModule


class PropagandaModule(LabelModule):
    name = "propaganda"
    title = "Propaganda technique"
    description = "Dominant persuasion technique (loaded language, appeal to fear, whataboutism, ...)."
    extra_columns = ("propaganda_techniques",)

    @property
    def none_label(self) -> str:
        return str(self.cfg.get("none_label", "none"))

    def derive(self, probabilities: dict[str, float]) -> dict[str, Any]:
        if probabilities.get(self.none_label, 0) >= max(probabilities.values(), default=0):
            return {"techniques": []}
        floor = float(self.cfg.get("min_probability", 0.2))
        found = sorted(((k, p) for k, p in probabilities.items() if k != self.none_label and p >= floor),
                       key=lambda kv: -kv[1])
        return {"techniques": [k for k, _ in found]}

    def to_columns(self, result: Any) -> dict[str, str]:
        if not result:
            return {}
        return {**super().to_columns(result), "propaganda_techniques": "|".join(result["techniques"])}

    def matches(self, result: Any, value: str) -> bool:
        if not result:
            return False
        if value == "any":
            return bool(result["techniques"])
        return result["label"] == value or value in result["techniques"]
