"""Offline IPTC Media Topics classification, batched by branch rather than a flat 1,000-label prompt."""
import asyncio
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

from ...core.engines import Question
from ...core.modules import Kind, Module


@lru_cache(maxsize=1)
def taxonomy():
    return json.loads(Path(__file__).with_name('taxonomy.json').read_text())


def flatten(nodes):
    for node in nodes:
        yield node
        yield from flatten(node.get('children', []))


def option_key(node):
    # The model sees meaningful names, never opaque medtop IDs.
    return re.sub(r'[^a-z0-9]+', '_', node['name'].lower()).strip('_')


class IptcModule(Module):
    name = 'iptc'
    title = 'IPTC'
    description = 'Classify news subjects using the official IPTC Media Topics names, definitions and hierarchy.'
    kind = Kind.LABEL
    engine_kinds = ('systemone', 'gliner2')
    output_columns = ('iptc', 'iptc_confidence', 'iptc_name', 'iptc_definition', 'iptc_path')
    default_batch_size = 32
    default_concurrency = 2

    @classmethod
    def reference(cls):
        return taxonomy()

    def __init__(self, ctx):
        super().__init__(ctx)
        self.tree = taxonomy()['tree']
        self.timing_key = hashlib.sha256((self.timing_key + taxonomy()['source_sha256']).encode()).hexdigest()[:20]
        self.nodes = {node['id']: node for node in flatten(self.tree)}
        self.max_chars = int(self.cfg.get('max_chars', 1500))
        self.max_depth = int(self.cfg.get('max_depth', 5))
        self.child_min = float(self.cfg.get('child_min_confidence', .5))
        self.review_below = float(self.cfg.get('review_below', .55))
        self.instructions = str(self.cfg.get('instructions', '')).strip()
        if self.engine.kind == 'gliner2':
            self.engine_options.setdefault('label_descriptions', True)
        if not 1 <= self.max_depth <= 5 or not 0 <= self.child_min <= 1 or not self.instructions:
            raise ValueError('iptc: max_depth must be 1–5, child_min_confidence 0–1, and instructions nonempty')

    def describe(self):
        return {**super().describe(), 'review_below': self.review_below,
                'labels': {key: node['definition'] for key, node in self.nodes.items()},
                'label_names': {key: node['name'] for key, node in self.nodes.items()},
                'taxonomy': {key: value for key, value in taxonomy().items() if key != 'tree'}}

    def question(self, nodes, parent=None):
        choices = {option_key(node): node for node in nodes}
        if len(choices) != len(nodes):
            raise ValueError('IPTC sibling names must map to distinct option keys')
        criteria = {key: node['definition'] for key, node in choices.items()}
        instructions = self.instructions
        if parent:
            criteria['broader_topic_only'] = 'The document supports the broader topic, but none of these more specific topics is clearly its main subject.'
            instructions += f" Choose a specific topic within {parent['name']}; choose broader_topic_only if no child is clearly supported."
        return Question('iptc_' + (parent['id'].split(':')[1] if parent else 'root'), 'choice', instructions, criteria), choices

    async def process_rows(self, job, idxs):
        live = [i for i in idxs if job.texts[i].strip()]
        out = {i: None for i in idxs}
        if not live:
            return [out[i] for i in idxs]
        texts = {i: job.texts[i][:self.max_chars] if self.max_chars else job.texts[i] for i in live}
        question, choices = self.question(self.tree)
        answers = await self.engine.classify([texts[i] for i in live], question, self.engine_options)
        for i, answer in zip(live, answers):
            if answer is None:
                continue
            node = choices[answer.label]
            path = [self.path_node(node, answer.confidence)]
            out[i] = self.result(node, path, 'max_depth' if self.max_depth == 1 else 'leaf')
            out[i]['top'] = [[choices[key]['id'], round(prob, 4)] for key, prob in sorted(answer.probabilities.items(), key=lambda kv: -kv[1])[:5]]
        for depth in range(1, self.max_depth):
            groups = defaultdict(list)
            for i in live:
                result = out[i]
                if result and len(result['path']) == depth and self.nodes[result['label']].get('children') and result['stop_reason'] not in {'broader_topic', 'low_confidence'}:
                    groups[result['label']].append(i)
            if not groups:
                break

            async def branch(parent_id, rows):
                parent = self.nodes[parent_id]
                question, choices = self.question(parent['children'], parent)
                answers = await self.engine.classify([texts[i] for i in rows], question, self.engine_options)
                for i, answer in zip(rows, answers):
                    if answer is None:
                        out[i]['stop_reason'] = 'low_confidence'
                    elif answer.label == 'broader_topic_only':
                        out[i]['stop_reason'] = 'broader_topic'
                    elif answer.confidence < self.child_min:
                        out[i]['stop_reason'] = 'low_confidence'
                        out[i]['next_level_confidence'] = answer.confidence
                    else:
                        node = choices[answer.label]
                        previous = out[i]
                        out[i] = {**self.result(node, [*previous['path'], self.path_node(node, answer.confidence)],
                                              'max_depth' if depth + 1 == self.max_depth and node.get('children') else 'leaf'),
                                  'top': previous['top']}
            await asyncio.gather(*(branch(parent_id, rows) for parent_id, rows in groups.items()))
        return [out[i] for i in idxs]

    @staticmethod
    def path_node(node, confidence):
        return {key: node[key] for key in ('id', 'name', 'definition')} | {'confidence': confidence}

    @staticmethod
    def result(node, path, reason):
        return {'label': node['id'], 'id': node['id'], 'name': node['name'], 'definition': node['definition'],
                'confidence': min(step['confidence'] for step in path), 'path': path, 'stop_reason': reason}

    def preview(self, result):
        return {key: result[key] for key in ('label', 'confidence', 'name')} if result else None

    def to_columns(self, result):
        if not result:
            return {}
        return {'iptc': result['id'], 'iptc_confidence': f"{result['confidence']:.4f}",
                'iptc_name': result['name'], 'iptc_definition': result['definition'],
                'iptc_path': json.dumps(result['path'], ensure_ascii=False)}

    def needs_review(self, result):
        return bool(result) and (result['confidence'] < self.review_below or result['stop_reason'] == 'low_confidence')

    def matches(self, result, value):
        return bool(result) and any(value in {node['id'], node['name']} for node in result['path'])

    def summarize(self, job, results):
        counts, roots = defaultdict(int), defaultdict(int)
        for result in results:
            if result:
                counts[result['label']] += 1
                roots[result['path'][0]['id']] += 1
        return {'counts': dict(counts), 'top_level_counts': dict(roots),
                'needs_review': sum(self.needs_review(result) for result in results)}
