"""Timing and throughput, for the dashboard and the benchmarks.

Three scopes, all in memory and bounded:
* `ModuleMetrics`: per job x module. Wall-clock window, busy time, batches, latency samples.
  `busy / wall` is the module's effective parallelism (how many batches were in flight).
* `Timeline`: per job, rows done per module, sampled every second while it runs.
* `CallMetrics`: per engine. Requests, errors, retries, in-flight, latency samples.
"""
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


def percentiles(samples: list[float], ps: tuple[int, ...] = (50, 95, 99)) -> dict[str, float | None]:
    if not samples:
        return {f"p{p}": None for p in ps}
    s = sorted(samples)
    return {f"p{p}": round(s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))], 1) for p in ps}


@dataclass
class ModuleMetrics:
    started_at: float | None = None
    finished_at: float | None = None
    rows: int = 0
    batches: int = 0
    busy_s: float = 0.0
    batch_ms: deque = field(default_factory=lambda: deque(maxlen=4096))
    row_ms: deque = field(default_factory=lambda: deque(maxlen=4096))

    def observe(self, rows: int, t0: float, t1: float) -> None:
        self.started_at = self.started_at or t0
        self.finished_at = t1
        self.rows += rows
        self.batches += 1
        dt = t1 - t0
        self.busy_s += dt
        self.batch_ms.append(dt * 1000)
        self.row_ms.append(dt * 1000 / max(1, rows))

    def snapshot(self, job_started: float | None, now: float) -> dict[str, Any]:
        wall = ((self.finished_at or now) - self.started_at) if self.started_at else 0.0
        base = job_started or self.started_at or now
        return {
            "rows": self.rows, "batches": self.batches,
            "start_s": round(self.started_at - base, 2) if self.started_at else None,
            "end_s": round(self.finished_at - base, 2) if self.finished_at else None,
            "wall_s": round(wall, 4), "busy_s": round(self.busy_s, 4),
            "parallelism": round(self.busy_s / wall, 2) if wall > 0 else None,
            "rows_per_s": round(self.rows / wall, 2) if wall > 0 else None,
            "batch_ms": {**percentiles(list(self.batch_ms)),
                         "mean": round(sum(self.batch_ms) / len(self.batch_ms), 1) if self.batch_ms else None},
            "row_ms": {**percentiles(list(self.row_ms)),
                       "mean": round(sum(self.row_ms) / len(self.row_ms), 1) if self.row_ms else None},
        }


class Timeline:
    """[(seconds since start, {module: rows done})], halved when it grows past `cap` points."""

    def __init__(self, cap: int = 1200):
        self.cap = cap
        self.points: list[tuple[float, dict[str, int]]] = []
        self.step = 1.0

    def sample(self, t: float, done: dict[str, int]) -> None:
        if self.points and t - self.points[-1][0] < self.step * 0.99:
            return
        self.points.append((round(t, 1), dict(done)))
        if len(self.points) > self.cap:
            self.points = self.points[::2]
            self.step *= 2


@dataclass
class CallMetrics:
    requests: int = 0
    errors: int = 0
    retries: int = 0
    inflight: int = 0
    items: int = 0
    latency_ms: deque = field(default_factory=lambda: deque(maxlen=4096))
    started: float = field(default_factory=time.time)

    def begin(self) -> float:
        self.inflight += 1
        return time.perf_counter()

    def end(self, t0: float, ok: bool, items: int = 1) -> None:
        self.inflight -= 1
        self.requests += 1
        self.items += items if ok else 0
        self.errors += 0 if ok else 1
        self.latency_ms.append((time.perf_counter() - t0) * 1000)

    def snapshot(self) -> dict[str, Any]:
        lat = list(self.latency_ms)
        return {"requests": self.requests, "errors": self.errors, "retries": self.retries,
                "inflight": self.inflight, "items": self.items,
                "latency_ms": {**percentiles(lat), "mean": round(sum(lat) / len(lat), 1) if lat else None}}
