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


@dataclass
class Platform:
    settings: Settings
    engines: EngineRegistry
    registry: ModuleRegistry
    jobs: JobManager
    _tasks: list[asyncio.Task] = field(default_factory=list)

    @classmethod
    def build(cls, settings: Settings, catalog: list[type[Module]]) -> "Platform":
        engines = EngineRegistry(settings, load_engine_config(settings.engines_path))
        modules = []
        for module_cls in catalog:
            cfg = load_module_config(settings.modules_dir, module_cls.name)
            if not cfg.get("enabled", True):
                log.info("module %s disabled by config", module_cls.name)
                continue
            ctx = ModuleContext(settings, cfg, engines, logging.getLogger(f"module.{module_cls.name}"))
            modules.append(module_cls(ctx))
        return cls(settings, engines, ModuleRegistry(modules), JobManager(settings))

    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        """Readiness waits run in the background: the UI shows models loading."""
        for e in self.engines.used:  # only engines an enabled module uses
            self._tasks.append(asyncio.create_task(e.wait_ready(), name=f"engine-{e.name}"))
        for m in self.registry:
            self._tasks.append(asyncio.create_task(m.start(), name=f"{m.name}-start"))
        self._tasks.append(asyncio.create_task(self.jobs.janitor(), name="janitor"))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.jobs.aclose()
        await asyncio.gather(*(m.aclose() for m in self.registry), self.engines.aclose(),
                             return_exceptions=True)

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
        return {"modules": [m.describe() for m in self.registry],
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
