"""Named entities with character spans, by a GLiNER2 extraction engine (zero-shot).

The labels in config/modules/ner.yaml ARE the prompt; their descriptions sharpen what each
label means. Rows go to the engine in batches; long documents are chunked by the service
and spans come back as offsets into the original text.
"""
import json
from typing import Any

from ...core.modules import Kind, Module, ModuleContext
from .grouping import group_entities


class NerModule(Module):
    name = "ner"
    title = "Entities"
    description = "People, organizations, places, dates, ... with exact positions in the text."
    kind = Kind.ENTITIES
    output_columns = ("NER",)
    engine_kinds = ("gliner2",)
    default_batch_size = 16
    default_concurrency = 2

    def __init__(self, ctx: ModuleContext):
        super().__init__(ctx)
        raw = self.cfg.get("labels") or []
        # A list of labels, or {label: description}.
        self.labels: dict[str, str] = ({str(k): str(v or "") for k, v in raw.items()} if isinstance(raw, dict)
                                       else {str(x): "" for x in raw})
        if not self.labels:
            raise ValueError("ner: config needs `labels`")
        self.spec = {k: v for k, v in self.labels.items()} if any(self.labels.values()) else list(self.labels)

    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "labels": self.labels}

    async def process_rows(self, job, idxs: list[int]) -> list[Any]:
        live = [i for i in idxs if job.texts[i].strip()]
        spans = dict(zip(live, await self.engine.extract("entities", [job.texts[i] for i in live], self.spec,
                                                         self.engine_options))) if live else {}
        return [{"spans": spans.get(i, []), "groups": group_entities(spans.get(i, []))} for i in idxs]

    def to_columns(self, result: Any) -> dict[str, str]:
        return {"NER": json.dumps(result["groups"] if result else {}, ensure_ascii=False)}

    def preview(self, result: Any) -> Any:
        return result["groups"] if result else None

    def matches(self, result: Any, value: str) -> bool:
        return bool(result) and value in result["groups"]

    def summarize(self, job, results: list[Any]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for r in results:
            for label, values in (r or {}).get("groups", {}).items():
                counts[label] = counts.get(label, 0) + len(values)
        return {"counts": dict(sorted(counts.items(), key=lambda kv: -kv[1]))}
