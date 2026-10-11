"""Named entities with character spans, by a GLiNER2 extraction engine (zero-shot).

The labels in config/modules/ner.yaml ARE the prompt; their descriptions sharpen what each
label means. Rows go to the engine in batches; long documents are chunked by the service
and spans come back as offsets into the original text.
"""
import json
from typing import Any

from ...core.modules import Kind, Module, ModuleContext
from .grouping import group_entities
from .validation import mask_code, validate_spans


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
        self.pii_labels = set(self.cfg.get('pii_labels') or [])
        self.include_numbers = bool(self.cfg.get('include_numbers', False))
        self.exclude_code = bool(self.cfg.get('exclude_code', True))
        self.money_currency = bool(self.cfg.get('money_requires_currency', True))

    def describe(self) -> dict[str, Any]:
        extra = {name: 'Detected by syntax/checksum validation; a match does not verify ownership or identity.' for name in self.pii_labels}
        if self.include_numbers:
            extra['number'] = 'Numeric expression; does not imply currency.'
        return {**super().describe(), "labels": {**self.labels, **extra}}

    async def process_rows(self, job, idxs: list[int]) -> list[Any]:
        live = [i for i in idxs if job.texts[i].strip()]
        texts = [mask_code(job.texts[i]) if self.exclude_code else job.texts[i] for i in live]
        spans = dict(zip(live, await self.engine.extract("entities", texts, self.spec,
                                                         self.engine_options))) if live else {}
        out = []
        for i in idxs:
            found = validate_spans(job.texts[i], spans.get(i, []), exclude_code=self.exclude_code,
                                   money_currency=self.money_currency, pii=self.pii_labels,
                                   include_numbers=self.include_numbers,
                                   region=str(self.cfg.get('phone_region', 'RO')))
            out.append({'spans': found, 'groups': group_entities(found)})
        return out

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
