"""Event type: what kind of real-world event, if any, the document reports."""
from ...core.kits.label import LabelModule


class EventModule(LabelModule):
    name = "event"
    title = "Event type"
    description = "Kind of real-world event reported (protest, attack, election, ...), or none."

    @property
    def no_event(self) -> str:
        return str(self.cfg.get("no_event_label", "no_event"))
