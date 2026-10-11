#!/usr/bin/env python3
"""Measure local tasks on the same deterministic 100-row multilingual sample."""
import asyncio
import json
import logging
import statistics
import time
from pathlib import Path

import pandas as pd
import yaml
from app.core.config import Settings
from app.core.engines import EngineRegistry, load_engine_config
from app.core.modules import ModuleContext
from app.core.pipeline import Job, JobRunner
from app.modules import CATALOG


async def main():
    settings = Settings()
    engines = EngineRegistry(settings, load_engine_config(settings.engines_path))
    frame = pd.read_csv(Path(settings.samples_dir) / 'sample-500.csv').fillna('').sample(n=100, random_state=20261011).sort_index().reset_index(drop=True)
    try:
        for cls in CATALOG:
            if cls.name not in {'language', 'ioc', 'temporal'}:
                continue
            cfg = yaml.safe_load((Path(settings.modules_dir) / f'{cls.name}.yaml').read_text())
            module = cls(ModuleContext(settings, cfg, engines, logging.getLogger(cls.name)))
            await module.start()
            warm = Job('warm', 'warm', frame.iloc[:4].copy(), [cls.name])
            await JobRunner(warm, [module]).run()
            trials = []
            for _ in range(3):
                job = Job('cpu', 'cpu', frame.copy(), [cls.name])
                started = time.perf_counter()
                await JobRunner(job, [module]).run()
                trials.append(time.perf_counter() - started)
            seconds = statistics.median(trials)
            print(json.dumps({'task': cls.name, 'rows': len(frame), 'median_s': seconds,
                              'rows_per_s': len(frame) / seconds, 'trials': trials,
                              'failed_rows': len(job.failed_rows()),
                              'note': 'Warm scheduler wall time; text-dependent CPU cost. No model calls.'}), flush=True)
    finally:
        await engines.aclose()


if __name__ == '__main__':
    asyncio.run(main())
