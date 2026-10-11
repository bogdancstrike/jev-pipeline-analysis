#!/usr/bin/env python3
"""Author-labelled EN/RO smoke checks; diagnostic coverage, not production accuracy."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

import pandas as pd
from app.core.config import Settings
from app.core.engines import load_engine_config
from benchmark_models import TASKS, VARIANTS, scenario


async def main(args):
    path = Path(args.cases)
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    settings = Settings()
    configs = load_engine_config(settings.engines_path)
    print(json.dumps({"type": "metadata", "cases_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "cases": len(cases),
                      "note": "Author-labelled synthetic smoke checks in English/Romanian. Acceptable labels are explicit; not representative production accuracy."}), flush=True)
    for cls in TASKS:
        if args.tasks and cls.name not in args.tasks.split(","):
            continue
        selected = [case for case in cases if cls.name in case["expected"]]
        frame = pd.DataFrame({"id": [case["id"] for case in selected], "text": [case["text"] for case in selected]})
        for engine in args.engines.split(","):
            for variant in VARIANTS[engine]:
                if args.variants and variant[0] not in args.variants.split(","):
                    continue
                try:
                    result = await scenario(settings, configs, cls, engine, variant, frame, 1, 0)
                    checks = [{"id": case["id"], "expected": case["expected"][cls.name], "prediction": prediction,
                               "correct": prediction in case["expected"][cls.name]} for case, prediction in zip(selected, result["predictions"])]
                    correct = sum(check["correct"] for check in checks)
                    print(json.dumps({"type": "result", "task": cls.name, "engine": engine, "variant": variant[0],
                                      "correct": correct, "cases": len(checks), "accuracy": round(correct / len(checks), 4), "checks": checks}), flush=True)
                except Exception as error:
                    print(json.dumps({"type": "error", "task": cls.name, "engine": engine, "variant": variant[0], "error": str(error)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="/benchmarks/quality-cases.jsonl")
    parser.add_argument("--engines", default="laya,gliner")
    parser.add_argument("--variants", default="")
    parser.add_argument("--tasks", default="")
    asyncio.run(main(parser.parse_args()))
