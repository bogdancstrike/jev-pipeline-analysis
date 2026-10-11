#!/usr/bin/env python3
"""Evaluate an explicit subject gate before extremist-narrative classification."""
import asyncio
import json
from pathlib import Path
import pandas as pd
from app.core.config import Settings
from app.core.engines import load_engine_config
from app.modules.extremism import ExtremismModule
from benchmark_models import scenario

async def main():
    settings = Settings()
    cases = [json.loads(line) for line in Path('/benchmarks/quality-cases.jsonl').read_text().splitlines() if 'extremism' in json.loads(line)['expected']]
    frame = pd.DataFrame({'id': [c['id'] for c in cases], 'text': [c['text'] for c in cases]})
    override = {'instructions': 'Is the document about violent extremism or terrorism? This includes endorsement, condemnation and neutral reporting of extremist violence. Ordinary emotions, advertisements, peaceful political criticism and religious practice are unrelated.', 'labels': {'extremism_or_terrorism': 'explicit discussion of violent extremism, terrorist attacks or extremist movements', 'unrelated': 'content about other subjects; not about violent extremism or terrorism'}}
    for engine,variant in [('laya',('lead-1500-512',1500,512)),('gliner',('lead-1500',1500,None))]:
        result = await scenario(settings, load_engine_config(settings.engines_path), ExtremismModule, engine, variant, frame, 1, 0, override)
        checks = [{'id': c['id'], 'prediction': p, 'expected': 'unrelated' if c['expected']['extremism'] == ['none'] else 'extremism_or_terrorism', 'confidence': conf} for c,p,conf in zip(cases,result['predictions'],result['confidences'])]
        print(json.dumps({'engine': engine, 'correct': sum(c['prediction']==c['expected'] for c in checks), 'cases': len(checks), 'checks': checks, 'override': override}),flush=True)

if __name__ == '__main__': asyncio.run(main())
