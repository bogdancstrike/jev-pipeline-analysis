"""Jobs and the scheduler that runs modules over them.

Scheduling is per row, not per stage: a row enters a module the moment it is done in all
of that module's requirements. So `language`, `category`, `ner`, `sentiment`, ... start
together, `entity_resolution` follows `ner` row by row, `relations` follows that, and the
job-scope `event_coreference` starts once `event` and `entity_resolution` covered every row.
GPU-bound modules overlap instead of waiting for each other.

Jobs live in process memory (one uvicorn worker on purpose); a restart loses them.
"""
import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import pandas as pd

from .config import Settings
from .modules import Module, Scope

log = logging.getLogger("pipeline")


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED)


@dataclass
class ModuleProgress:
    done: int = 0
    errors: int = 0


@dataclass
class Job:
    id: str
    filename: str
    df: pd.DataFrame
    modules: list[str]
    max_text_chars: int = 60_000
    status: JobStatus = JobStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    results: dict[str, list[Any]] = field(default_factory=dict)
    errors: dict[str, dict[int, str]] = field(default_factory=dict)
    progress: dict[str, ModuleProgress] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)  # per-module scratch space for this job
    version: int = 0                                      # bumped on every change; drives SSE

    def __post_init__(self) -> None:
        self.df = self.df.reset_index(drop=True)
        self.ids: list[str] = [str(v) for v in self.df["id"].tolist()]
        self.texts: list[str] = [(t or "")[: self.max_text_chars] for t in self.df["text"].tolist()]
        for name in self.modules:
            self.results.setdefault(name, [None] * self.total)
            self.errors.setdefault(name, {})
            self.progress.setdefault(name, ModuleProgress())

    @property
    def total(self) -> int:
        return len(self.df)

    @property
    def done(self) -> int:
        """Rows every module has finished with."""
        return min((p.done for p in self.progress.values()), default=0)

    def result(self, module: str, i: int) -> Any:
        return self.results[module][i] if module in self.results else None

    def module_state(self, module: str, factory: Callable[[], Any]) -> Any:
        if module not in self.state:
            self.state[module] = factory()
        return self.state[module]

    def failed_rows(self) -> set[int]:
        return {i for errs in self.errors.values() for i in errs}

    def touch(self) -> None:
        self.version += 1

    def elapsed(self) -> float:
        if not self.started_at:
            return 0.0
        return (self.finished_at or time.time()) - self.started_at

    def snapshot(self) -> dict[str, Any]:
        elapsed = self.elapsed()
        work_total = self.total * max(1, len(self.progress))
        work_done = sum(p.done for p in self.progress.values())
        rate = self.done / elapsed if elapsed > 0 else 0.0
        work_rate = work_done / elapsed if elapsed > 0 else 0.0
        running = self.status == JobStatus.RUNNING
        return {
            "id": self.id, "filename": self.filename, "status": str(self.status), "error": self.error,
            "modules": self.modules, "total": self.total, "done": self.done,
            "progress": {k: {"done": p.done, "errors": p.errors} for k, p in self.progress.items()},
            "percent": round(100 * work_done / work_total, 1) if work_total else 0.0,
            "failed_rows": len(self.failed_rows()),
            "rows_per_s": round(rate, 2),
            "eta_s": round((work_total - work_done) / work_rate) if running and work_rate > 0 else None,
            "elapsed_s": round(elapsed, 1),
            "created_at": self.created_at,
        }


class JobRunner:
    """Runs one job through a dependency-closed, topologically ordered module list."""

    def __init__(self, job: Job, modules: list[Module]):
        self.job, self.modules = job, modules
        self.by_name = {m.name: m for m in modules}
        self.dependents: dict[str, list[Module]] = {m.name: [] for m in modules}
        for m in modules:
            for r in m.requires:
                self.dependents[r].append(m)
        n = job.total
        self.waiting = {m.name: [len(m.requires)] * n for m in modules if m.scope == Scope.ROW}
        self.queues: dict[str, asyncio.Queue] = {m.name: asyncio.Queue() for m in modules if m.scope == Scope.ROW}
        self.enqueued = {name: 0 for name in self.queues}
        self.complete = {m.name: asyncio.Event() for m in modules}

    async def run(self) -> None:
        for m in self.modules:
            if m.scope == Scope.ROW and not m.requires:
                for i in range(self.job.total):
                    self._enqueue(m, i)
        tasks = []
        for m in self.modules:
            if m.scope == Scope.ROW:
                tasks += [self._worker(m) for _ in range(max(1, m.concurrency))]
            else:
                tasks.append(self._run_job_scope(m))
        await asyncio.gather(*tasks)

    def _enqueue(self, m: Module, i: int) -> None:
        q = self.queues[m.name]
        q.put_nowait(i)
        self.enqueued[m.name] += 1
        if self.enqueued[m.name] == self.job.total:  # nothing more will come: stop the workers
            for _ in range(max(1, m.concurrency)):
                q.put_nowait(None)

    async def _worker(self, m: Module) -> None:
        q = self.queues[m.name]
        while True:
            first = await q.get()
            if first is None:
                return
            batch = [first]
            while len(batch) < m.batch_size:
                try:
                    nxt = q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if nxt is None:
                    q.put_nowait(None)  # leave the stop signal for the next get
                    break
                batch.append(nxt)
            try:
                results = await m.process_rows(self.job, batch)
                if len(results) != len(batch):
                    raise RuntimeError(f"{m.name} returned {len(results)} results for {len(batch)} rows")
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - one bad batch must not kill the job
                log.warning("job %s: %s failed on rows %s: %s", self.job.id, m.name, batch[:5], e)
                self._fail(m, batch, e)
            else:
                for i, r in zip(batch, results):
                    self.job.results[m.name][i] = r
            await self._rows_done(m, batch)

    async def _run_job_scope(self, m: Module) -> None:
        await asyncio.gather(*(self.complete[r].wait() for r in m.requires))
        rows = list(range(self.job.total))
        try:
            results = await m.process_job(self.job)
            self.job.results[m.name] = list(results)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("job %s: %s failed", self.job.id, m.name)
            self._fail(m, rows, e)
        await self._rows_done(m, rows)

    def _fail(self, m: Module, rows: list[int], e: Exception) -> None:
        msg = str(e) or type(e).__name__
        for i in rows:
            self.job.errors[m.name][i] = msg
        self.job.progress[m.name].errors += len(rows)

    async def _rows_done(self, m: Module, rows: list[int]) -> None:
        p = self.job.progress[m.name]
        p.done += len(rows)
        if p.done >= self.job.total and not self.complete[m.name].is_set():
            try:
                await m.finalize(self.job)
            except Exception:  # noqa: BLE001
                log.exception("job %s: %s finalize failed", self.job.id, m.name)
            self.complete[m.name].set()
        self.job.touch()
        # Dependents still run on rows that failed here: they see `None` and degrade.
        for d in self.dependents[m.name]:
            if d.scope != Scope.ROW:
                continue
            waiting = self.waiting[d.name]
            for i in rows:
                waiting[i] -= 1
                if waiting[i] == 0:
                    self._enqueue(d, i)


class JobManager:
    def __init__(self, settings: Settings):
        self.s = settings
        self.jobs: dict[str, Job] = {}
        self._slots = asyncio.Semaphore(settings.max_parallel_jobs)
        self._tasks: dict[str, asyncio.Task] = {}

    def submit(self, filename: str, df: pd.DataFrame, modules: list[Module]) -> Job:
        job = Job(id=uuid.uuid4().hex, filename=filename, df=df, modules=[m.name for m in modules],
                  max_text_chars=self.s.max_text_chars)
        self.jobs[job.id] = job
        task = asyncio.create_task(self._run(job, modules), name=f"job-{job.id}")
        self._tasks[job.id] = task
        task.add_done_callback(lambda _: self._tasks.pop(job.id, None))
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def all(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    def cancel(self, job: Job) -> bool:
        task = self._tasks.get(job.id)
        if job.status.terminal or task is None:
            return False
        task.cancel()
        return True

    def delete(self, job: Job) -> None:
        self.cancel(job)
        self.jobs.pop(job.id, None)

    async def _run(self, job: Job, modules: list[Module]) -> None:
        try:
            async with self._slots:
                job.status, job.started_at = JobStatus.RUNNING, time.time()
                job.touch()
                await JobRunner(job, modules).run()
                job.status = JobStatus.DONE
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            log.info("job %s cancelled", job.id)
        except Exception as e:  # noqa: BLE001 - surface anything to the UI
            log.exception("job %s failed", job.id)
            job.status, job.error = JobStatus.FAILED, str(e)
        finally:
            job.finished_at = time.time()
            job.started_at = job.started_at or job.finished_at
            job.touch()

    async def janitor(self, every_s: float = 300) -> None:
        while True:
            await asyncio.sleep(every_s)
            cutoff = time.time() - self.s.job_ttl_s
            for jid in [j.id for j in self.jobs.values() if j.finished_at and j.finished_at < cutoff]:
                self.jobs.pop(jid, None)

    async def aclose(self) -> None:
        tasks = list(self._tasks.values())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
