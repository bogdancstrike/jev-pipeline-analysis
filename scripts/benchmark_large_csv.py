#!/usr/bin/env python3
"""Real large-file throughput of topic classification plus local enrichment, without saved runs.

This is a four-task workload, not the full pipeline. Run in a Compose backend one-off
with the app/scripts mounted and redirect stdout to benchmarks/runs/. Each file is
processed in chunks so foreground jobs can finish between chunks.
"""
import asyncio
import hashlib
import json
import logging
from pathlib import Path
import time

import httpx
import pandas as pd
import yaml

from app.core.config import Settings
from app.core.engines import EngineRegistry, load_engine_config
from app.core.modules import ModuleContext
from app.core.pipeline import Job, JobRunner
from app.modules import CATALOG


async def idle(client):
    started = time.perf_counter()
    while True:
        response = await client.get('http://backend:8000/api/jobs')
        response.raise_for_status()
        if not any(j['status'] in ('queued', 'running') for j in response.json()):
            return time.perf_counter() - started
        await asyncio.sleep(2)


async def main():
    settings = Settings()
    registry = EngineRegistry(settings, load_engine_config(settings.engines_path))
    modules = []
    for cls in CATALOG:
        if cls.name in {'language', 'category', 'ioc', 'temporal'}:
            config = yaml.safe_load((Path(settings.modules_dir) / f'{cls.name}.yaml').read_text())
            modules.append(cls(ModuleContext(settings, config, registry, logging.getLogger(cls.name))))
    try:
        await asyncio.gather(*(m.start() for m in modules))
        await asyncio.gather(*(e.wait_ready() for e in registry.used))
        async with httpx.AsyncClient(timeout=30) as client:
            for count in [5000, 15000, 30000]:
                path = Path(settings.samples_dir) / f'sample-{count}.csv'
                start = time.perf_counter()
                frame = pd.read_csv(path).fillna('')
                load_s = time.perf_counter() - start
                if count == 5000:
                    await idle(client)
                    warm = Job('warm', 'warm', frame.iloc[:8].copy(), [m.name for m in modules])
                    await JobRunner(warm, modules).run()
                elapsed, wait_s, errors, done = 0, 0, 0, 0
                for offset in range(0, len(frame), 500):
                    wait_s += await idle(client)
                    chunk = frame.iloc[offset:offset + 500].copy().reset_index(drop=True)
                    job = Job('large-bench', path.name, chunk, [m.name for m in modules])
                    start = time.perf_counter()
                    await JobRunner(job, modules).run()
                    elapsed += time.perf_counter() - start
                    errors += len(job.failed_rows())
                    done += len(chunk)
                    print(json.dumps({'type': 'progress', 'file': path.name, 'done': done, 'rows': len(frame), 'processing_s': elapsed}), flush=True)
                print(json.dumps({'type': 'result', 'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                  'tasks': [m.name for m in modules], 'rows': len(frame), 'unique_texts': frame.text.nunique(),
                                  'processing_s': elapsed, 'load_s': load_s, 'foreground_wait_s': wait_s,
                                  'rows_per_s': len(frame) / elapsed, 'failed_rows': errors,
                                  'settings': {m.name: m.cfg for m in modules}, 'repeats': 1,
                                  'note': 'Real four-task workload; chunked in groups of 500. Not full-pipeline timing. Waiting for foreground work excluded.'}), flush=True)
    finally:
        await registry.aclose()


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
