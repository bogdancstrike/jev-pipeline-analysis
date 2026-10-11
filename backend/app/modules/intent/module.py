"""Communicative intent: what the author is trying to achieve with the text."""
from ...core.kits.label import LabelModule


class IntentModule(LabelModule):
    name = "intent"
    title = "Intent"
    description = "What the author is trying to do: inform, persuade, mobilize, recruit, threaten, ..."
