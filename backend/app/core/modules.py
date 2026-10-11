"""The module contract: everything core needs to schedule, store, filter, export and show
a module's work, and nothing about *how* the module does it.

A module is one enrichment (language, topic, entities, sentiment, ...). It lives in its
own package under `app/modules/`, owns its config file (`config/modules/<name>.yaml`) and
talks to the rest of the system only through this contract:

* `requires` names other modules whose per-row results it reads (`job.result(name, i)`).
  Core runs a row through a module as soon as that row is done in every requirement.
* `scope = ROW` modules process rows (in batches of `batch_size`, `concurrency` batches at a
  time); `scope = JOB` modules run once, after their requirements finished every row, and
  return one result per row (e.g. event coreference, which compares rows with each other).
* Results are plain JSON-able values. `preview` is the compact form for table rows,
  `to_columns` the flat form for the CSV, `summarize` the job-level aggregate for the UI,
  `matches` answers row filters such as `sentiment:negative`.
"""
from __future__ import annotations

import logging
import hashlib
import json
from abc import ABC
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

from .config import Settings
from .engines import Engine, EngineRegistry

if TYPE_CHECKING:
    from .pipeline import Job


class Scope(StrEnum):
    ROW = "row"
    JOB = "job"


class Kind(StrEnum):
    """How the UI renders a result. New kinds need a renderer in the frontend registry."""
    LABEL = "label"            # {label, confidence, top: [[label, p], ...], ...extras}
    ENTITIES = "entities"      # {spans: [...], groups: {label: [surface, ...]}}
    RESOLVED = "resolved"      # {entities: [{id, name, label, mentions, spans}]}
    RELATIONS = "relations"    # {relations: [{head, head_id, relation, tail, tail_id, confidence}]}
    CLUSTER = "cluster"        # {cluster, size, peers: [idx], confidence}
    RECORD = "record"          # {record_type: [{field: {text, confidence} | [...]}]}


@dataclass
class ModuleContext:
    """What core hands a module: settings, its own config file, the engine registry."""
    settings: Settings
    config: dict[str, Any]
    engines: EngineRegistry
    log: logging.Logger


class Module(ABC):
    name: ClassVar[str]
    title: ClassVar[str]
    description: ClassVar[str]
    kind: ClassVar[Kind]
    requires: ClassVar[tuple[str, ...]] = ()
    scope: ClassVar[Scope] = Scope.ROW
    output_columns: ClassVar[tuple[str, ...]] = ()
    default_batch_size: ClassVar[int] = 1
    default_concurrency: ClassVar[int] = 4
    # Engine kinds this module can run on; () = needs no model engine (pure CPU logic).
    engine_kinds: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def reference(cls) -> dict[str, Any] | None:
        """Optional offline reference vocabulary, fetched separately from task discovery."""
        return None

    def __init__(self, ctx: ModuleContext):
        self.ctx = ctx
        self.cfg = ctx.config
        self.log = ctx.log
        self.batch_size = int(self.cfg.get("batch_size", self.default_batch_size))
        self.concurrency = int(self.cfg.get("concurrency", self.default_concurrency))
        # Per-task engine overrides (e.g. which checkpoint alias), passed on every call.
        self.engine_options: dict[str, Any] = dict(self.cfg.get("engine_options") or {})
        self.engine: Engine | None = None
        if self.engine_kinds:
            name = self.cfg.get("engine")
            if not name:
                raise ValueError(f"{self.name}: config needs `engine:` (one of kinds {self.engine_kinds})")
            self.engine = ctx.engines.get(str(name), self.engine_kinds)
        # Saved timings are comparable only while both task and engine settings match.
        timing_cfg = {k: v for k, v in self.cfg.items() if k not in ("profile", "enabled", "default_on")}
        self.timing_key = hashlib.sha256(json.dumps(
            {"task": timing_cfg, "engine": self.engine.cfg if self.engine else None},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]

    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        """Background readiness wait (load a model, wait for a service). Must return when ready."""

    @property
    def ready(self) -> bool:
        return self.engine.ready if self.engine else True

    async def aclose(self) -> None:
        pass

    def describe(self) -> dict[str, Any]:
        """Static facts for the UI: what it is, how to render it, what it depends on."""
        return {"name": self.name, "title": self.title, "description": self.description,
                "kind": str(self.kind), "scope": str(self.scope), "requires": list(self.requires),
                "columns": list(self.output_columns),
                "engine": self.engine.name if self.engine else None,
                "engine_kind": self.engine.kind if self.engine else "local",
                "timing_key": self.timing_key,
                "default_on": bool(self.cfg.get("default_on", True)),
                # For the UI's info point: how fast, measured where (see docs/BENCHMARKS.md).
                "profile": dict(self.cfg.get("profile") or {})}

    # ---------------------------------------------------------------- work
    async def process_rows(self, job: Job, idxs: list[int]) -> list[Any]:
        """ROW scope: one result per index, same order. Raise to fail the whole batch."""
        raise NotImplementedError

    async def process_job(self, job: Job) -> list[Any]:
        """JOB scope: one result per row of the job."""
        raise NotImplementedError

    async def finalize(self, job: Job) -> None:
        """Called once this module has finished every row (e.g. to settle cross-row ids)."""

    # ---------------------------------------------------------------- presentation
    def to_columns(self, result: Any) -> dict[str, str]:
        return {}

    def preview(self, result: Any) -> Any:
        return result

    def needs_review(self, result: Any) -> bool:
        return False

    def matches(self, result: Any, value: str) -> bool:
        return False

    def summarize(self, job: Job, results: list[Any]) -> dict[str, Any] | None:
        return None
