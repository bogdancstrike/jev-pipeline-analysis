#!/usr/bin/env python3
"""Compare task/model/context choices without changing settings or creating dashboard runs.

Run inside the backend container (it has network access to model services and their keys):
  docker compose exec -T backend sh -c 'cat > /tmp/benchmark_models.py' < scripts/benchmark_models.py
  docker compose exec -T backend python /tmp/benchmark_models.py --engines laya,gliner --rows 100 --repeats 3

One JSON object per line, flushed after each scenario. Redirect stdout to an artifact under
benchmarks/runs/. Model calls are real; timing includes the production scheduler, token
budget handling, HTTP transport, batching, postprocessing and derived scores. No persistence.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import logging
import statistics
import time
from pathlib import Path

import pandas as pd
import yaml

from app.core.config import Settings
from app.core.engines import EngineRegistry, load_engine_config
from app.core.kits.label import LabelModule
from app.core.modules import ModuleContext
from app.core.pipeline import Job, JobRunner
from app.modules import CATALOG

TASKS = [cls for cls in CATALOG if issubclass(cls, LabelModule)]
VARIANTS = {
    "laya": [("lead-1500-512", 1500, 512), ("lead-3500-1024", 3500, 1024), ("full-2048", 0, 2048)],
    "gliner": [("lead-1500", 1500, None), ("lead-3500", 3500, None)],
    "kev": [("lead-1500", 1500, None), ("lead-3500", 3500, None), ("full", 0, None)],
}


def quality(task, predictions, frame):
    column = {"category": "gold_topic", "event": "gold_event"}.get(task)
    if not column or column not in frame:
        return {"accuracy": None, "labelled_rows": 0}
    labelled = [(i, str(value).split("|")) for i, value in enumerate(frame[column]) if pd.notna(value) and str(value).strip()]
    correct = sum(bool(predictions[i]) and predictions[i].get("label") in expected for i, expected in labelled)
    by_lang = {}
    for language in sorted(set(str(frame.iloc[i].get("lang", "unknown")) for i, _ in labelled)):
        subset = [(i, expected) for i, expected in labelled if str(frame.iloc[i].get("lang", "unknown")) == language]
        by_lang[language] = {"rows": len(subset), "accuracy": round(sum(bool(predictions[i]) and predictions[i].get("label") in expected for i, expected in subset) / len(subset), 4)}
    return {"accuracy": round(correct / len(labelled), 4) if labelled else None,
            "labelled_rows": len(labelled), "quality_by_language": by_lang}


async def scenario(settings, configs, cls, engine_name, variant, frame, repeats, warmup, overrides=None):
    name, max_chars, context = variant
    cfg = yaml.safe_load((Path(settings.modules_dir) / f"{cls.name}.yaml").read_text())
    cfg.update(overrides or {})
    original_engine = cfg["engine"]
    options = dict(cfg.get("engine_options") or {}) if engine_name == original_engine else dict((overrides or {}).get("engine_options") or {})
    cfg.update(engine=engine_name, max_chars=max_chars)
    engine_configs = copy.deepcopy(configs)
    if context:
        options["max_len"] = context
    if engine_name == "gliner":
        options.setdefault("label_descriptions", False)
        options.update(threshold=0.0, batch_size=8)
    cfg["engine_options"] = options
    registry = EngineRegistry(settings, engine_configs)
    module = cls(ModuleContext(settings, cfg, registry, logging.getLogger(cls.name)))
    engine = module.engine
    try:
        await asyncio.wait_for(engine.wait_ready(), 30)
        if engine.info.get("degraded"):
            raise RuntimeError(engine.info["degraded"])
        if warmup:
            job = Job("warmup", "warmup", frame.iloc[:warmup].copy(), [cls.name])
            await asyncio.wait_for(JobRunner(job, [module]).run(), 120)
        trials, predictions = [], None
        for trial in range(repeats):
            job = Job(f"benchmark-{trial}", "benchmark", frame.copy(), [cls.name])
            start = time.perf_counter()
            await asyncio.wait_for(JobRunner(job, [module]).run(), 300)
            elapsed = time.perf_counter() - start
            predictions = job.results[cls.name]
            trials.append({"wall_s": round(elapsed, 4), "rows_per_s": round(job.total / elapsed, 3),
                           "failed_rows": len(job.failed_rows()), "missing_results": sum(result is None for result in predictions)})
        await engine.refresh()
        seconds = statistics.median(trial["wall_s"] for trial in trials)
        return {"task": cls.name, "engine": engine_name, "variant": name, "rows": len(frame),
                "max_chars": max_chars, "context_tokens": context, "engine_options": options,
                "median_s": round(seconds, 4), "rows_per_s": round(len(frame) / seconds, 3),
                "trials": trials, "health": engine.info, "metrics": engine.metrics.snapshot(),
                "predictions": [result.get("label") if result else None for result in predictions],
                "confidences": [result.get("confidence") if result else None for result in predictions],
                **quality(cls.name, predictions, frame)}
    finally:
        await registry.aclose()


async def main(args):
    settings = Settings()
    path = Path(settings.samples_dir) / args.sample
    frame = pd.read_csv(path).fillna("")
    frame = frame[frame["text"].str.strip().ne("")]
    frame = frame.sample(n=min(args.rows, len(frame)), random_state=args.seed).sort_index().reset_index(drop=True)
    configs = load_engine_config(settings.engines_path)
    print(json.dumps({"type": "metadata", "sample": args.sample, "sample_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "ids": frame["id"].astype(str).tolist(), "rows": len(frame), "seed": args.seed,
                      "repeats": args.repeats, "warmup_rows": args.warmup,
                      "languages": frame["lang"].value_counts().to_dict() if "lang" in frame else {},
                      "chars": {"min": int(frame.text.str.len().min()), "median": int(frame.text.str.len().median()), "max": int(frame.text.str.len().max())},
                      "quality_note": "Synthetic template corpus; gold_topic accepts multiple valid topics. Other tasks have no accuracy labels here."}), flush=True)
    for cls in TASKS:
        if args.tasks and cls.name not in args.tasks.split(","):
            continue
        for engine in args.engines.split(","):
            for variant in VARIANTS[engine]:
                if args.variants and variant[0] not in args.variants.split(","):
                    continue
                try:
                    result = await scenario(settings, configs, cls, engine, variant, frame, args.repeats, args.warmup)
                    print(json.dumps({"type": "result", **result}), flush=True)
                except Exception as error:
                    print(json.dumps({"type": "error", "task": cls.name, "engine": engine, "variant": variant[0], "error": str(error)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engines", default="laya,gliner")
    parser.add_argument("--sample", default="sample-500.csv")
    parser.add_argument("--rows", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261011)
    parser.add_argument("--tasks", default="")
    parser.add_argument("--variants", default="")
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main(parser.parse_args()))
