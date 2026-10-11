"""Entity resolution as a module: one registry per job, fed row by row from `ner`."""
import json
from typing import Any

from ...core.modules import Kind, Module, ModuleContext
from .resolver import EntityRegistry


class EntityResolutionModule(Module):
    name = "entity_resolution"
    title = "Resolved entities"
    description = ("Links mentions of the same entity within a row and across rows "
                   "(aliases, acronyms, inflected forms), with a stable id per entity.")
    kind = Kind.RESOLVED
    requires = ("ner",)
    output_columns = ("entities",)
    default_batch_size = 32
    default_concurrency = 1  # the registry is shared per job: keep its updates sequential

    def __init__(self, ctx: ModuleContext):
        super().__init__(ctx)
        self.groups = {str(g): [str(x) for x in labels] for g, labels in (self.cfg.get("groups") or {}).items()}
        if not self.groups:
            raise ValueError("entity_resolution: config needs `groups`")
        self.aliases = [[str(x) for x in names] for names in self.cfg.get("aliases") or []]
        self.stopwords = tuple(str(w) for w in self.cfg.get("acronym_stopwords") or ())
        self.ignore = tuple(str(w) for w in self.cfg.get("ignore_mentions") or ())

    def registry(self, job) -> EntityRegistry:
        return job.module_state(self.name, lambda: EntityRegistry(
            self.groups, self.aliases, acronym_groups=("organization",), stopwords=self.stopwords,
            ignore=self.ignore))

    async def process_rows(self, job, idxs: list[int]) -> list[Any]:
        reg = self.registry(job)
        out = []
        for i in idxs:
            ner = job.result("ner", i)
            out.append({"entities": reg.resolve_row(i, ner["spans"] if ner else [])})
        return out

    async def finalize(self, job) -> None:
        self.registry(job).settle(job.results[self.name])

    def to_columns(self, result: Any) -> dict[str, str]:
        ents = [{"id": e["id"], "name": e.get("canonical", e["name"]), "label": e["label"]}
                for e in (result or {}).get("entities", [])]
        return {"entities": json.dumps(ents, ensure_ascii=False)}

    def preview(self, result: Any) -> Any:
        if not result:
            return None
        return [{"id": e["id"], "name": e.get("canonical", e["name"]), "label": e["label"]}
                for e in result["entities"]]

    def matches(self, result: Any, value: str) -> bool:
        return bool(result) and any(e["id"] == value for e in result["entities"])

    def summarize(self, job, results: list[Any]) -> dict[str, Any]:
        reg = job.state.get(self.name)
        if reg is None:
            return {"entities": 0, "top": []}
        return {"entities": reg.count(), "top": reg.top(int(self.cfg.get("summary_top", 20)))}
