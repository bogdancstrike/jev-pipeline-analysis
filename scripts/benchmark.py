#!/usr/bin/env python3
"""Benchmark the running stack through its public API, the way a user runs jobs.

    python3 scripts/benchmark.py --sample sample-500.csv --each        # every module alone
    python3 scripts/benchmark.py --sample sample-5000.csv --modules all
    python3 scripts/benchmark.py --sample sample-500.csv --modules language,ner,category

For each scenario: start a server-side sample job, poll until it stops, read
/api/jobs/{id}/metrics, sample GPU utilization and memory with nvidia-smi meanwhile.
Raw results go to benchmarks/runs/<timestamp>.json; a markdown table is printed.

Measure on a quiet machine: other jobs (or a desktop on the same GPU) skew the numbers.
"""
import argparse
import json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def api(base: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(base + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


class GpuSampler(threading.Thread):
    def __init__(self, every_s: float = 0.5):
        super().__init__(daemon=True)
        self.every_s, self.util, self.mem, self._halt = every_s, [], [], threading.Event()

    def run(self) -> None:
        while not self._halt.is_set():
            try:
                out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                                      "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
                u, m = out.stdout.strip().splitlines()[0].split(",")
                self.util.append(int(u))
                self.mem.append(int(m))
            except Exception:  # noqa: BLE001 - no GPU / no nvidia-smi: report nothing
                pass
            self._halt.wait(self.every_s)

    def stop(self) -> dict:
        self._halt.set()
        self.join()
        if not self.util:
            return {}
        return {"gpu_util_avg": round(sum(self.util) / len(self.util)), "gpu_util_max": max(self.util),
                "vram_max_mb": max(self.mem)}


def run(base: str, sample: str, modules: list[str]) -> dict:
    gpu = GpuSampler()
    gpu.start()
    t0 = time.time()
    job = api(base, "/api/jobs/sample", {"sample": sample, "modules": modules})
    while job["status"] not in ("done", "failed", "cancelled"):
        time.sleep(0.5)
        job = api(base, f"/api/jobs/{job['id']}")
    m = api(base, f"/api/jobs/{job['id']}/metrics")
    return {"sample": sample, "modules": job["modules"], "requested": modules, "status": job["status"],
            "rows": job["total"], "failed_rows": job["failed_rows"], "wall_s": m["wall_s"],
            "client_s": round(time.time() - t0, 2), "rows_per_s": round(job["total"] / m["wall_s"], 2),
            "per_module": m["modules"], "engines": m["engines"], **gpu.stop()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default="http://localhost:8088")
    ap.add_argument("--sample", default="sample-500.csv")
    ap.add_argument("--modules", default="", help="comma list, or 'all'")
    ap.add_argument("--each", action="store_true", help="one scenario per module (with its dependencies)")
    ap.add_argument("--label", default="")
    a = ap.parse_args()

    catalog = [m["name"] for m in api(a.base, "/api/config")["modules"]]
    if a.each:
        scenarios = [[m] for m in catalog]
    elif a.modules == "all":
        scenarios = [catalog]
    else:
        scenarios = [[m.strip() for m in a.modules.split(",") if m.strip()]]

    results = []
    print(f"| scenario | modules run | rows | wall s | articles/s | GPU avg % | VRAM max MB | failed |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    for s in scenarios:
        r = run(a.base, a.sample, s)
        results.append(r)
        name = "all" if s == catalog else ",".join(s)
        print(f"| {name} | {len(r['modules'])} | {r['rows']} | {r['wall_s']} | {r['rows_per_s']} | "
              f"{r.get('gpu_util_avg', '-')} | {r.get('vram_max_mb', '-')} | {r['failed_rows']} |", flush=True)

    out = ROOT / "benchmarks" / "runs" / f"{time.strftime('%Y%m%d-%H%M%S')}{'-' + a.label if a.label else ''}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"base": a.base, "sample": a.sample, "results": results}, indent=1))
    print(f"\nraw: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
