"""The coordinator: builds the enabled modules, starts them, and answers questions that
span modules (health, summaries, row views, the CSV export). Routes talk to this, never to
a module directly, so a module can change without touching the API.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import Settings
from .csv_io import ERROR_MARK, build_output
from .engines import EngineRegistry, load_engine_config
from .modules import Module, ModuleContext
from .pipeline import Job, JobManager
from .registry import ModuleRegistry
from .store import MemoryStore, Store, make_store

log = logging.getLogger("platform")

PREVIEW_CHARS = 240


def load_module_config(modules_dir: str, name: str) -> dict[str, Any]:
    path = Path(modules_dir) / f"{name}.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    return data


def effective_config(defaults: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    """YAML defaults with the admin override on top. Top-level keys replace: an edited label
    list is the new list, not a merge (a merge could never delete a label)."""
    return {**defaults, **(override or {})}


@dataclass
class Platform:
    settings: Settings
    engines: EngineRegistry
    registry: ModuleRegistry
    jobs: JobManager
    catalog: list[type[Module]] = field(default_factory=list)
    store: Store = field(default_factory=MemoryStore)
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    _tasks: list[asyncio.Task] = field(default_factory=list)
    _started_engines: set[str] = field(default_factory=set)

    @classmethod
    def build(cls, settings: Settings, catalog: list[type[Module]], store: Store | None = None) -> "Platform":
        engines = EngineRegistry(settings, load_engine_config(settings.engines_path))
        p = cls(settings, engines, ModuleRegistry([]), JobManager(settings), catalog=list(catalog),
                store=store or make_store(settings.store_url))
        p.registry = p._build_registry({})
        return p

    # ---------------------------------------------------------------- configuration
    def defaults(self, name: str) -> dict[str, Any]:
        return load_module_config(self.settings.modules_dir, name)

    def module_class(self, name: str) -> type[Module]:
        for c in self.catalog:
            if c.name == name:
                return c
        raise KeyError(name)

    def _construct(self, module_cls: type[Module], cfg: dict[str, Any]) -> Module:
        ctx = ModuleContext(self.settings, cfg, self.engines, logging.getLogger(f"module.{module_cls.name}"))
        return module_cls(ctx)

    def _build_registry(self, overrides: dict[str, dict[str, Any]]) -> ModuleRegistry:
        """Every enabled module from YAML + overrides. Raises on any invalid config."""
        modules = []
        for module_cls in self.catalog:
            cfg = effective_config(self.defaults(module_cls.name), overrides.get(module_cls.name))
            if not cfg.get("enabled", True):
                log.info("module %s disabled by config", module_cls.name)
                continue
            modules.append(self._construct(module_cls, cfg))
        return ModuleRegistry(modules)

    async def apply_overrides(self, overrides: dict[str, dict[str, Any]]) -> None:
        """Validate the whole module graph with these overrides, then swap it in. Running jobs
        keep the module instances they started with; new jobs get the new ones."""
        registry = self._build_registry(overrides)  # raises ValueError -> nothing changes
        self.registry, self.overrides = registry, overrides
        self._start_new_engines()

    def _start_new_engines(self) -> None:
        for e in self.engines.used:
            if e.name not in self._started_engines and any(m.engine is e for m in self.registry):
                self._started_engines.add(e.name)
                self._tasks.append(asyncio.create_task(e.wait_ready(), name=f"engine-{e.name}"))

    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        """Readiness waits run in the background: the UI shows models loading."""
        try:
            await self.store.start()
            stored = await self.store.overrides()
            if stored:
                try:
                    await self.apply_overrides(stored)
                    log.info("applied admin overrides for %s", sorted(stored))
                except ValueError as e:  # a bad stored override must not keep the service down
                    log.error("ignoring stored overrides, they no longer validate: %s", e)
        except Exception:  # noqa: BLE001 - the pipeline runs on YAML defaults without a DB
            log.exception("settings store unavailable; running on YAML defaults")
        self._start_new_engines()
        for m in self.registry:
            self._tasks.append(asyncio.create_task(m.start(), name=f"{m.name}-start"))
        self._tasks.append(asyncio.create_task(self.jobs.janitor(), name="janitor"))
        self.jobs.on_finish = self._persist_run

    async def _persist_run(self, job: Job) -> None:
        try:
            m = self.job_metrics(job)
            await self.store.save_run({"id": job.id, "filename": job.filename, "status": str(job.status),
                                       "total": job.total, "modules": job.modules, "created_at": job.created_at,
                                       "wall_s": m["wall_s"], "rows_per_s": m["rows_per_s"],
                                       "metrics": {"modules": m["modules"], "peak_rows_per_s": m["peak_rows_per_s"],
                                                   "failed_rows": job.snapshot()["failed_rows"]}})
        except Exception:  # noqa: BLE001 - history is best effort
            log.exception("could not persist run %s", job.id)

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.jobs.aclose()
        await asyncio.gather(*(m.aclose() for m in self.registry), self.engines.aclose(),
                             return_exceptions=True)
        await self.store.close()

    # ---------------------------------------------------------------- facts
    def health(self) -> dict[str, Any]:
        modules = {m.name: {"ready": m.ready, "engine": m.engine.name if m.engine else None}
                   for m in self.registry}
        engines = {e.name: {**e.status(), "modules": [m.name for m in self.registry if m.engine is e]}
                   for e in self.engines.used}
        ready = all(v["ready"] for v in modules.values())
        return {"status": "ready" if ready else "loading", "engines": engines, "modules": modules}

    def describe(self) -> dict[str, Any]:
        s = self.settings
        modules = []
        for m in self.registry:
            d = m.describe()
            d["dependents"] = [x.name for x in self.registry if m.name in x.requires]
            d["shares_engine_with"] = [x.name for x in self.registry if x is not m and m.engine and x.engine is m.engine]
            modules.append(d)
        return {"modules": modules,
                "engines": {e.name: {"kind": e.kind, "description": e.description} for e in self.engines.used},
                "defaults": self.registry.defaults(),
                "limits": {"max_upload_mb": s.max_upload_mb, "max_rows": s.max_rows},
                "samples": self.samples()}

    def samples(self, all_files: bool = False) -> list[dict[str, Any]]:
        """Sample CSVs on the server, smallest first. With `manifest.json` (written by
        scripts/generate_sample.py) only entries marked `ui` are offered, with row counts;
        `all_files` also returns the rest (the 50k benchmark set, test fixtures)."""
        root = Path(self.settings.samples_dir)
        if not root.is_dir():
            return []
        described: dict[str, dict[str, Any]] | None = None
        manifest = root / "manifest.json"
        if manifest.is_file():
            try:
                described = {m["file"]: m for m in json.loads(manifest.read_text(encoding="utf-8"))}
            except (ValueError, KeyError, TypeError):
                log.warning("ignoring unreadable %s", manifest)
        out = []
        for f in root.glob("*.csv"):
            m = (described or {}).get(f.name, {})
            if described is not None and not all_files and not m.get("ui"):
                continue
            out.append({"file": f.name, "rows": m.get("rows"), "bytes": f.stat().st_size,
                        "words_median": m.get("words_median"), "languages": m.get("languages", [])})
        return sorted(out, key=lambda x: (x["rows"] is None, x["rows"] or 0, x["bytes"]))

    def sample_path(self, name: str) -> Path:
        """Only a file the listing contains: never a path built from user input."""
        for s in self.samples(all_files=True):
            if s["file"] == name:
                return Path(self.settings.samples_dir) / s["file"]
        raise KeyError(name)

    def output_columns(self) -> list[str]:
        return [c for m in self.registry for c in m.output_columns]

    # ---------------------------------------------------------------- per job
    def modules_of(self, job: Job) -> list[Module]:
        return [self.registry.get(n) for n in job.modules if n in self.registry]

    def summary(self, job: Job) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for m in self.modules_of(job):
            s = m.summarize(job, job.results[m.name]) or {}
            out[m.name] = {**s, "errors": len(job.errors[m.name])}
        return {"modules": out, "needs_review": sum(1 for i in range(job.total) if self.review_flags(job, i))}

    def review_flags(self, job: Job, i: int) -> list[str]:
        return [m.name for m in self.modules_of(job) if m.needs_review(job.results[m.name][i])]

    def row_matches(self, job: Job, i: int, filters: list[tuple[str, str]], review: bool,
                    errors: bool, query: str) -> bool:
        if query and query not in job.ids[i].casefold() and query not in job.texts[i].casefold():
            return False
        if errors and not any(i in job.errors[n] for n in job.modules):
            return False
        if review and not self.review_flags(job, i):
            return False
        for name, value in filters:
            if name not in job.results or not self.registry.get(name).matches(job.results[name][i], value):
                return False
        return True

    def row_item(self, job: Job, i: int) -> dict[str, Any]:
        mods = self.modules_of(job)
        return {"idx": i, "id": job.ids[i], "preview": job.texts[i][:PREVIEW_CHARS],
                "results": {m.name: m.preview(job.results[m.name][i]) for m in mods},
                "review": self.review_flags(job, i),
                "errors": [n for n in job.modules if i in job.errors[n]]}

    def row_detail(self, job: Job, i: int) -> dict[str, Any]:
        return {"idx": i, "id": job.ids[i], "text": job.texts[i],
                "results": {n: job.results[n][i] for n in job.modules},
                "review": self.review_flags(job, i),
                "errors": {n: job.errors[n][i] for n in job.modules if i in job.errors[n]}}

    def job_metrics(self, job: Job) -> dict[str, Any]:
        import time
        now = time.time()
        modules = {}
        for m in self.modules_of(job):
            modules[m.name] = {**job.metrics[m.name].snapshot(job.started_at, now),
                               "engine": m.engine.name if m.engine else None,
                               "errors": len(job.errors[m.name])}
        pts = job.timeline.points
        overall = [(t, min(d.values()) if d else 0) for t, d in pts]
        peak = max(((b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(overall, overall[1:]) if b[0] > a[0]), default=0.0)
        wall = job.elapsed()
        return {"job": job.snapshot(), "wall_s": round(wall, 2),
                "rows_per_s": round(job.done / wall, 2) if wall > 0 else None,
                "peak_rows_per_s": round(peak, 2), "modules": modules,
                "timeline": [{"t": t, "done": d} for t, d in pts],
                "engines": self.engine_metrics()}

    def engine_metrics(self) -> dict[str, Any]:
        return {e.name: {"kind": e.kind, "ready": e.ready, **e.metrics.snapshot()} for e in self.engines.used}

    def export(self, job: Job) -> bytes:
        cols: dict[str, list[str]] = {}
        for m in self.modules_of(job):
            for c in m.output_columns:
                cols[c] = [""] * job.total
            for i, r in enumerate(job.results[m.name]):
                if i in job.errors[m.name]:
                    if m.output_columns:
                        cols[m.output_columns[0]][i] = ERROR_MARK
                    continue
                for c, v in m.to_columns(r).items():
                    cols[c][i] = v
        return build_output(job.df, cols, self.settings.csv_formula_escape)
