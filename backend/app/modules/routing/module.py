"""Routing: which desk or team should handle the document (or discard it)."""
from ...core.kits.label import LabelModule


class RoutingModule(LabelModule):
    name = "routing"
    title = "Routing"
    description = "Which desk should pick the text up: cyber, security, politics, economy, ... or discard."
