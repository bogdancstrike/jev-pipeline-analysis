"""Structured fields: typed records pulled out of the text (what / where / when / who ...).

The schema lives in config/modules/fields.yaml, one record type per entry, fields written
as "name::str|list::description". GLiNER2 fills each field from spans of the text itself,
so values are grounded in the document, never invented.
"""
import json
from typing import Any

from ...core.modules import Kind, Module, ModuleContext


class FieldsModule(Module):
    name = "fields"
    title = "Structured fields"
    description = "Typed records extracted from the text (event: what, where, when, who, casualties, ...)."
    kind = Kind.RECORD
    output_columns = ("fields",)
    engine_kinds = ("gliner2",)
    default_batch_size = 8
    default_concurrency = 1

    def __init__(self, ctx: ModuleContext):
        super().__init__(ctx)
        self.records: dict[str, list[str]] = {str(k): [str(f) for f in v] for k, v in (self.cfg.get("records") or {}).items()}
        if not self.records:
            raise ValueError("fields: config needs `records`")
        self.max_chars = int(self.cfg.get("max_chars", 0))  # 0 = whole text

    def describe(self) -> dict[str, Any]:
        fields = {rec: [f.split("::")[0] for f in fs] for rec, fs in self.records.items()}
        return {**super().describe(), "records": fields}

    async def process_rows(self, job, idxs: list[int]) -> list[Any]:
        live = [i for i in idxs if job.texts[i].strip()]
        cut = (lambda t: t[: self.max_chars]) if self.max_chars else (lambda t: t)
        found = dict(zip(live, await self.engine.extract("structures", [cut(job.texts[i]) for i in live], self.records,
                                                         self.engine_options))) if live else {}
        return [self._clean(found.get(i)) for i in idxs]

    @staticmethod
    def _value(v: Any) -> Any:
        if isinstance(v, dict):
            return {"text": v.get("text"), "confidence": round(float(v.get("confidence", 0)), 4)} if v.get("text") else None
        if isinstance(v, list):
            vals = [FieldsModule._value(x) for x in v]
            return [x for x in vals if x] or None
        return {"text": v, "confidence": None} if v else None

    def _clean(self, raw: Any) -> dict[str, Any] | None:
        """{record: [{field: value | [values]}]} with empty fields and empty records dropped."""
        if not raw:
            return None
        out: dict[str, list[dict[str, Any]]] = {}
        for rec, instances in raw.items():
            items = instances if isinstance(instances, list) else [instances]
            kept = []
            for inst in items:
                if isinstance(inst, dict):
                    fields = {k: v for k, v in ((k, self._value(v)) for k, v in inst.items()) if v}
                    if fields:
                        kept.append(fields)
            if kept:
                out[rec] = kept
        return out or None

    @staticmethod
    def _flat(v: Any) -> Any:
        if isinstance(v, list):
            return [x["text"] for x in v]
        return v["text"]

    def to_columns(self, result: Any) -> dict[str, str]:
        flat = {rec: [{k: self._flat(v) for k, v in inst.items()} for inst in insts]
                for rec, insts in (result or {}).items()}
        return {"fields": json.dumps(flat, ensure_ascii=False)}

    def preview(self, result: Any) -> Any:
        if not result:
            return None
        rec, insts = next(iter(result.items()))
        return {"record": rec, "fields": {k: self._flat(v) for k, v in insts[0].items()}, "count": len(insts)}

    def matches(self, result: Any, value: str) -> bool:
        """`fields:<name>` = rows where that field was found in any record."""
        return bool(result) and any(value in inst for insts in result.values() for inst in insts)

    def summarize(self, job, results: list[Any]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for r in results:
            seen = {k for insts in (r or {}).values() for inst in insts for k in inst}
            for k in seen:
                counts[k] = counts.get(k, 0) + 1
        return {"counts": dict(sorted(counts.items(), key=lambda kv: -kv[1]))}
