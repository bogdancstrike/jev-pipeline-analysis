"""Scale: 50,000 real-length articles through the real scheduler and CPU modules, with instant
fake engines, so what is measured is the backend's own overhead (it must stay far below GPU
time). Opt in: `pytest -m scale -s` (needs samples/sample.csv: scripts/generate_sample.py)."""
import asyncio
import time

import pytest

from app.core.csv_io import parse_csv

from .conftest import SAMPLES, build_platform

pytestmark = pytest.mark.scale


@pytest.mark.asyncio
async def test_50k_rows_core_overhead():
    path = SAMPLES / "sample.csv"
    if not path.exists():
        pytest.skip("generate samples/sample.csv first")
    t0 = time.perf_counter()
    df = parse_csv(path.read_bytes(), 200_000)
    parse_s = time.perf_counter() - t0
    assert len(df) == 50_000

    p = build_platform()
    for e in p.engines.used:
        await e.wait_ready()
    modules = p.registry.closure(["language", "ner", "entity_resolution", "event", "event_coreference", "sentiment"])
    t0 = time.perf_counter()
    job = p.jobs.submit("sample.csv", df, modules)
    while not job.status.terminal:
        await asyncio.sleep(0.5)
    run_s = time.perf_counter() - t0
    assert job.status == "done", job.error

    t0 = time.perf_counter(); summary = p.summary(job); summary_s = time.perf_counter() - t0
    t0 = time.perf_counter(); snap = job.snapshot(); snap_s = time.perf_counter() - t0
    t0 = time.perf_counter(); csv_bytes = p.export(job); export_s = time.perf_counter() - t0
    rows = [i for i in range(job.total) if p.row_matches(job, i, [("sentiment", "negative")], False, False, "")]
    print(f"\nparse {parse_s:.1f}s | run {run_s:.1f}s ({job.total / run_s:.0f} rows/s) | summary {summary_s:.2f}s | "
          f"snapshot {snap_s * 1000:.1f}ms | export {export_s:.1f}s ({len(csv_bytes) / 1e6:.0f} MB) | "
          f"entities {summary['modules']['entity_resolution']['entities']:,} | filtered {len(rows):,}")
    # Budgets: overhead must be small next to GPU time (~0.04 s/article/task on the RTX 3080).
    assert parse_s < 30 and summary_s < 5 and snap_s < 0.05 and export_s < 60
    assert run_s < 600, "core overhead alone would dominate a 50k run"
