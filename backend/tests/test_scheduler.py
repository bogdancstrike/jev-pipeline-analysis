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
