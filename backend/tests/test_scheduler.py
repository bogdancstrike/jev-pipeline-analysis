"""The coordinator's scheduling contract, with toy modules (no services involved)."""
import asyncio
import logging

import pandas as pd
import pytest

from app.core.errors import InvalidInput
from app.core.modules import Kind, Module, ModuleContext, Scope
from app.core.pipeline import JobManager, JobStatus
from app.core.registry import ModuleRegistry

from .conftest import make_settings


def ctx(**cfg) -> ModuleContext:
    return ModuleContext(make_settings(), cfg, None, logging.getLogger("test"))  # type: ignore[arg-type]


class Upper(Module):
    name, title, description, kind = "upper", "Upper", "", Kind.LABEL
    default_batch_size = 2

    async def process_rows(self, job, idxs):
        if any("boom" in job.texts[i] for i in idxs):
            raise RuntimeError("boom")
        return [job.texts[i].upper() for i in idxs]


class Length(Module):
    name, title, description, kind = "length", "Length", "", Kind.LABEL
    requires = ("upper",)
    seen: list = []

    async def process_rows(self, job, idxs):
        out = []
        for i in idxs:
            up = job.result("upper", i)
            self.seen.append((i, up))
            out.append(len(up) if up else None)
        return out


class Total(Module):
    name, title, description, kind = "total", "Total", "", Kind.CLUSTER
    requires = ("length",)
    scope = Scope.JOB

    async def process_job(self, job):
        total = sum(x or 0 for x in job.results["length"])
        return [total] * job.total


class Slow(Module):
    name, title, description, kind = "slow", "Slow", "", Kind.LABEL

    async def process_rows(self, job, idxs):
        await asyncio.sleep(10)
        return [None] * len(idxs)


def registry(*classes) -> ModuleRegistry:
    return ModuleRegistry([c(ctx()) for c in classes])


async def wait(job, timeout=5.0):
    for _ in range(int(timeout / 0.01)):
        if job.status.terminal:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"job still {job.status}")


def test_closure_adds_dependencies_in_order():
    reg = registry(Upper, Length, Total)
    assert [m.name for m in reg.closure(["total"])] == ["upper", "length", "total"]
    with pytest.raises(InvalidInput):
        reg.closure(["nope"])


def test_missing_dependency_is_a_startup_error():
    with pytest.raises(ValueError, match="requires"):
        registry(Length)


@pytest.mark.asyncio
async def test_rows_flow_through_dependencies_and_job_scope_runs_last():
    reg = registry(Upper, Length, Total)
    jm = JobManager(make_settings())
    df = pd.DataFrame({"id": ["a", "b", "c"], "text": ["ab", "boom", "cde"]})
    job = jm.submit("t.csv", df, reg.closure(["total"]))
    await wait(job)
    assert job.status == JobStatus.DONE
    assert job.results["upper"] == [None, None, "CDE"] or job.results["upper"][2] == "CDE"
    # The failing batch is recorded per row; dependents still ran on those rows (with None).
    assert set(job.errors["upper"]) & {1}
    assert job.progress["length"].done == 3
    assert job.results["total"] == [sum(x or 0 for x in job.results["length"])] * 3


@pytest.mark.asyncio
async def test_cancel_stops_a_running_job():
    reg = registry(Slow)
    jm = JobManager(make_settings())
    job = jm.submit("t.csv", pd.DataFrame({"id": ["1"], "text": ["x"]}), reg.closure(["slow"]))
    await asyncio.sleep(0.05)
    assert jm.cancel(job)
    await wait(job)
    assert job.status == JobStatus.CANCELLED and not jm.cancel(job)


def test_progress_is_not_pinned_at_zero_by_a_job_level_module():
    """Regression: '0 rows/s' while running. A job-scope module (coreference) reports all rows
    at the end; it must not hold 'records done' and throughput at 0 meanwhile."""
    import time

    from app.core.pipeline import Job, ModuleProgress
    job = Job(id="j", filename="f.csv", df=pd.DataFrame({"id": ["1", "2"], "text": ["a", "b"]}),
              modules=["upper", "total"], job_scoped={"total"})
    job.status, job.started_at = JobStatus.RUNNING, time.time() - 10
    job.progress = {"upper": ModuleProgress(done=2), "total": ModuleProgress(done=0)}
    snap = job.snapshot()
    assert snap["done"] == 2 and snap["rows_per_s"] > 0 and snap["percent"] == 50.0


class _Engine:  # a stand-in: only identity matters for alignment
    ready = True


SHARED = _Engine()


class FastOnEngine(Module):
    name, title, description, kind = "fast", "Fast", "", Kind.LABEL
    default_batch_size, default_concurrency = 2, 1
    max_lead = 0

    async def process_rows(self, job, idxs):
        slow_done = job.progress["slow"].done
        FastOnEngine.max_lead = max(FastOnEngine.max_lead, idxs[0] - slow_done)
        return [1] * len(idxs)


class SlowOnEngine(Module):
    name, title, description, kind = "slow", "Slow", "", Kind.LABEL
    default_batch_size, default_concurrency = 2, 1

    async def process_rows(self, job, idxs):
        await asyncio.sleep(0.005)
        return [1] * len(idxs)


@pytest.mark.asyncio
async def test_tasks_sharing_an_engine_stay_row_aligned():
    fast, slow = FastOnEngine(ctx()), SlowOnEngine(ctx())
    fast.engine = slow.engine = SHARED  # same engine object -> peers
    jm = JobManager(make_settings())
    df = pd.DataFrame({"id": [str(i) for i in range(200)], "text": ["x"] * 200})
    job = jm.submit("t.csv", df, ModuleRegistry([fast, slow]).closure(["fast", "slow"]))
    await wait(job, timeout=20)
    assert job.status == JobStatus.DONE
    window = fast.batch_size * fast.concurrency * 2
    assert FastOnEngine.max_lead <= window + fast.batch_size, FastOnEngine.max_lead


@pytest.mark.asyncio
async def test_delete_waits_for_terminal_history_save():
    """Deletion cannot race an on_finish callback that is already saving a done job."""
    jm = JobManager(make_settings())
    saving, release = asyncio.Event(), asyncio.Event()
    saved = []

    async def persist(job):
        saving.set()
        await release.wait()
        saved.append(job.id)

    jm.on_finish = persist
    job = jm.submit("t.csv", pd.DataFrame({"id": ["1"], "text": ["x"]}), registry(Upper).closure(["upper"]))
    await asyncio.wait_for(saving.wait(), 2)
    assert job.status == JobStatus.DONE
    deletion = asyncio.create_task(jm.delete(job))
    await asyncio.sleep(0)
    assert not deletion.done()
    release.set()
    await asyncio.wait_for(deletion, 2)
    assert saved == [job.id]
    assert jm.get(job.id) is None


@pytest.mark.asyncio
async def test_delete_queued_job_leaves_running_job_alone():
    jm = JobManager(make_settings(max_parallel_jobs=1))
    modules = registry(Slow).closure(["slow"])
    frame = pd.DataFrame({"id": ["1"], "text": ["x"]})
    first, queued = jm.submit("first.csv", frame, modules), jm.submit("queued.csv", frame, modules)
    await asyncio.sleep(0)
    assert first.status == JobStatus.RUNNING and queued.status == JobStatus.QUEUED
    await jm.delete(queued)
    assert jm.get(queued.id) is None and first.status == JobStatus.RUNNING
    await jm.aclose()
