#!/usr/bin/env python3
"""Evaluate NER guards on code, counts, identifiers and a deterministic news sample."""
import argparse
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
from app.modules.ner import NerModule

CASES = [
    {'id': 'code', 'text': 'from framework.decorators import kafka_handler\n@kafka_handler(name="example")\nasync def example(message, consumer_name):\n    return message\nThe example processed 100,000 messages at 293.99 messages per second. FastAPI, Kafka, Flask and Redis are software projects.'},
    {'id': 'news-en', 'text': 'Microsoft CEO Satya Nadella met President Klaus Iohannis in Bucharest, Romania on 10 May 2024. Microsoft invested $100,000 in the project.'},
    {'id': 'news-ro', 'text': 'Președintele Nicușor Dan s-a întâlnit cu reprezentanții NATO la București. Compania Dacia a investit 100.000 de euro în România.'},
    {'id': 'counts', 'text': 'The worker processed 100 000 messages in 72.34 seconds. The pool contains 32 workers. A donation of 50 euros was received.'},
    {'id': 'identifiers', 'text': 'Email analyst@example.org. Phone +40 722 123 456. Public test fixture CNP 1630615123457; wrong checksum 1630615123458. Passport AB1234567. IBAN RO49 AAAA 1B31 0075 9384 0000.'},
]


async def main(args):
    settings = Settings()
    engines = EngineRegistry(settings, load_engine_config(settings.engines_path))
    news = pd.read_csv(Path(settings.samples_dir) / 'sample-500.csv').fillna('').sample(n=30, random_state=20261011).reset_index(drop=True)
    special = list(CASES)
    if args.private_input:
        special.append({'id': 'private-user-document', 'text': json.loads(Path(args.private_input).read_text())['text']})
    frame = pd.concat([pd.DataFrame(special), news[['id', 'text']]], ignore_index=True)
    baseline = yaml.safe_load(json.loads(Path('/benchmarks/baseline-configs.json').read_text())['ner'])
    baseline.update(exclude_code=False, money_requires_currency=False, pii_labels=[], include_numbers=False)
    current = yaml.safe_load((Path(settings.modules_dir) / 'ner.yaml').read_text())
    outputs = {}
    try:
        for variant, cfg in [('previous', baseline), ('validated', current)]:
            module = NerModule(ModuleContext(settings, cfg, engines, logging.getLogger('ner')))
            await module.engine.wait_ready()
            warm = Job('warm', 'warm', frame.iloc[:2].copy(), ['ner'])
            await JobRunner(warm, [module]).run()
            trials = []
            for _ in range(3):
                job = Job('ner-bench', 'ner-bench', frame.copy(), ['ner'])
                start = time.perf_counter()
                await JobRunner(job, [module]).run()
                trials.append(time.perf_counter() - start)
            results = job.results['ner']
            outputs[variant] = results
            checks = [{'id': case['id'], 'spans': results[i]['spans']} for i, case in enumerate(CASES)]
            private = results[len(CASES)]['spans'] if args.private_input else []
            bad = [s for s in private if s['text'].lower() in {'example', 'examples', 'message', 'kafka_handler'} and s['label'] in {'person', 'organization', 'company'}]
            seconds = statistics.median(trials)
            print(json.dumps({'variant': variant, 'rows': len(frame), 'median_s': seconds, 'rows_per_s': len(frame) / seconds,
                              'trials': trials, 'failed_rows': len(job.failed_rows()), 'checks': checks,
                              'private_document': {'tested': bool(args.private_input), 'reported_false_positive_mentions': len(bad),
                                                   'money_mentions': sum(s['label'] == 'money' for s in private),
                                                   'number_mentions': sum(s['label'] == 'number' for s in private)}}), flush=True)
        old_total = retained = new_total = 0
        for previous, current in zip(outputs['previous'][len(special):], outputs['validated'][len(special):]):
            old = {(s['start'], s['end'], s['label']) for s in previous['spans']}
            new = {(s['start'], s['end'], s['label']) for s in current['spans']}
            old_total += len(old)
            new_total += len(new)
            retained += len(old & new)
        print(json.dumps({'type': 'agreement', 'news_documents': len(news), 'previous_spans': old_total, 'new_spans': new_total,
                          'retained': retained, 'retention': retained / max(1, old_total), 'note': 'Span agreement, not extraction accuracy.'}), flush=True)
        if args.private_output:
            Path(args.private_output).write_text(json.dumps({name: results[len(CASES)] for name, results in outputs.items()}, ensure_ascii=False))
    finally:
        await engines.aclose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-input')
    parser.add_argument('--private-output')
    asyncio.run(main(parser.parse_args()))
