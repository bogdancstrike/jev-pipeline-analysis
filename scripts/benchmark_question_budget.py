#!/usr/bin/env python3
"""Measure whether preserving more question text improves the new classifiers."""
import asyncio
import json
from pathlib import Path
import pandas as pd
from app.core.config import Settings
from app.core.engines import load_engine_config
from benchmark_models import TASKS, scenario

async def main():
    s = Settings()
    cases = [json.loads(line) for line in Path('/benchmarks/quality-cases.jsonl').read_text().splitlines()]
    for cls in TASKS:
        if cls.name not in {'genre','emotion','extremism','propaganda'}:continue
        selected = [c for c in cases if cls.name in c['expected']]
        frame = pd.DataFrame({'id':[c['id'] for c in selected], 'text':[c['text'] for c in selected]})
        for budget in [128,192,256,384,512]:
            r = await scenario(s,load_engine_config(s.engines_path),cls,'laya',('lead-3500-1024',3500,1024),frame,1,0,{'engine_options':{'head_max_len':budget}})
            checks = [{'id':c['id'],'prediction':p,'correct':p in c['expected'][cls.name]} for c,p in zip(selected,r['predictions'])]
            print(json.dumps({'task':cls.name,'head_max_len':budget,'correct':sum(c['correct'] for c in checks),'cases':len(checks),'checks':checks}),flush=True)

if __name__=='__main__':asyncio.run(main())
