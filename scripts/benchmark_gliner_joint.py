#!/usr/bin/env python3
"""Isolated GLiNER joint-schema comparison. Stop GPU services before running.

docker compose run --rm --no-deps -T -v "$PWD/config:/config:ro" \
  -v "$PWD/samples:/samples:ro" extractor python - < scripts/benchmark_gliner_joint.py
"""
import csv
import json
import random
import os
import statistics
import time
from pathlib import Path

import torch
import yaml
from gliner2 import AutoExtractor
from app.main import _entities, _relations

rows = list(csv.DictReader(open('/samples/sample-500.csv')))
ids = sorted(random.Random(20261011).sample(range(len(rows)), int(os.environ.get('BENCH_ROWS', '60'))))
texts = [rows[i]['text'] for i in ids]
ner = yaml.safe_load(Path('/config/modules/ner.yaml').read_text())
rel = yaml.safe_load(Path('/config/modules/relations.yaml').read_text())
labels = ner['labels']
types = [key for key in rel['labels'] if key != rel['none_label']]
torch.cuda.set_per_process_memory_fraction(float(os.environ.get('BENCH_GPU_FRACTION', '0.12')))
model = AutoExtractor.from_pretrained('fastino/gliner2.5-multi-v1').to(device='cuda', dtype=torch.bfloat16).eval()
batch_size = int(os.environ.get('BENCH_BATCH_SIZE', '1'))
kw = dict(batch_size=batch_size, include_confidence=True, include_spans=True, chunk_size=384, chunk_overlap=64)
schema = model.create_schema().entities(labels, threshold=0.5).relations(types, threshold=0.3)

def run(mode, batch):
    if mode == 'joint':
        out = model.batch_extract_long(batch, schema, threshold=0.3, **kw)
        return [(_entities(o), _relations(o)) for o in out]
    entities = model.batch_extract_entities_long(batch, labels, threshold=0.5, **kw)
    relations = model.batch_extract_relations_long(batch, types, threshold=0.3, **kw)
    return [(_entities(e), _relations(r)) for e, r in zip(entities, relations)]

def keys(result, kind):
    if kind == 0:
        return {(s['start'], s['end'], s['label']) for s in result[0]}
    return {(s['head'].get('start'), s['head'].get('end'), s['relation'], s['tail'].get('start'), s['tail'].get('end')) for s in result[1] if s['score'] >= 0.4}

print(json.dumps({'type': 'metadata', 'ids': [rows[i]['id'] for i in ids], 'rows': len(texts), 'batch_size': batch_size, 'repeats': 3,
                  'live_services_running': True, 'gpu_fraction_cap': os.environ.get('BENCH_GPU_FRACTION', '0.12'),
                  'note': 'Output agreement versus separate schemas is not ground-truth accuracy.'}), flush=True)
outputs = {}
with torch.inference_mode():
    for mode in ['separate', 'joint']:
        run(mode, texts[:2])
        times = []
        torch.cuda.reset_peak_memory_stats()
        for _ in range(3):
            torch.cuda.synchronize()
            start = time.perf_counter()
            outputs[mode] = run(mode, texts)
            torch.cuda.synchronize()
            times.append(time.perf_counter() - start)
        print(json.dumps({'type': 'result', 'mode': mode, 'seconds': times, 'median_s': statistics.median(times),
                          'rows_per_s': len(texts) / statistics.median(times), 'peak_vram_mb': torch.cuda.max_memory_allocated() / 2**20,
                          'entities': sum(len(o[0]) for o in outputs[mode]), 'relations': sum(len(keys(o, 1)) for o in outputs[mode])}), flush=True)
for kind, name in enumerate(['entities', 'relations']):
    old = [keys(o, kind) for o in outputs['separate']]
    new = [keys(o, kind) for o in outputs['joint']]
    common = sum(len(a & b) for a, b in zip(old, new))
    print(json.dumps({'type': 'agreement', 'task': name, 'separate': sum(map(len, old)), 'joint': sum(map(len, new)),
                      'common': common, 'retention': common / max(1, sum(map(len, old))),
                      'precision_vs_separate': common / max(1, sum(map(len, new)))}), flush=True)
