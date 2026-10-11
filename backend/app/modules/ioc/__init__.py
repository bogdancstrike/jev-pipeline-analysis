"""Offline IOC syntax extraction. Matches are observable artifacts, not maliciousness verdicts."""
import ipaddress
import json
import re
from ...core.modules import Kind, Module
from ..ner.grouping import group_entities
from ..ner.validation import code_ranges

_PATTERNS = [
    ('url', re.compile(r"\b(?:https?|hxxps?)://[^\s<>\"']+", re.I)),
    ('ipv4', re.compile(r'(?<![\w.])(?:\d{1,3}(?:\.|\[\.\]|\(\.\))){3}\d{1,3}(?!\w|\.\d)')),
    ('ipv6', re.compile(r'(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])')),
    ('sha256', re.compile(r'\b[0-9a-fA-F]{64}\b')),
    ('sha1', re.compile(r'\b[0-9a-fA-F]{40}\b')),
    ('md5', re.compile(r'\b[0-9a-fA-F]{32}\b')),
    ('domain', re.compile(r'(?<![\w@.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.|\[\.\]|\(\.\)))+(?:com|org|net|edu|gov|mil|int|info|biz|io|dev|app|xyz|[a-z]{2})(?![\w-]|\.\w)', re.I)),
]


def extract_iocs(text, labels):
    out = []
    ranges = code_ranges(text)
    for kind, pattern in _PATTERNS:
        if kind not in labels:
            continue
        for match in pattern.finditer(text):
            value = match.group().rstrip('.,;!?')
            if kind == 'url':
                for opening, closing in [('(', ')'), ('[', ']')]:
                    while value.endswith(closing) and value.count(closing) > value.count(opening):
                        value = value[:-1]
            start, end = match.start(), match.start() + len(value)
            if any(s['start'] < end and start < s['end'] for s in out):
                continue
            if kind == 'domain' and any(a < end and start < b for a, b in ranges):
                continue
            normalized = value.replace('[.]', '.').replace('(.)', '.')
            if kind == 'url':
                normalized = re.sub(r'^hxxp', 'http', normalized, flags=re.I)
            elif kind in {'ipv4', 'ipv6'}:
                try:
                    addr = ipaddress.ip_address(normalized)
                    if addr.version != (4 if kind == 'ipv4' else 6):
                        continue
                    normalized = str(addr)
                except ValueError:
                    continue
            elif kind in {'domain', 'md5', 'sha1', 'sha256'}:
                normalized = normalized.lower()
            out.append({'start': start, 'end': end, 'text': value, 'label': kind, 'normalized': normalized,
                        'score': 1.0, 'source': 'pattern', 'validation': 'syntax'})
    return sorted(out, key=lambda s: s['start'])


class IocModule(Module):
    name = 'ioc'
    title = 'Cyber indicators'
    description = 'Validated URLs, domains, IP addresses and hashes, including defanged indicators; no network calls.'
    kind = Kind.ENTITIES
    output_columns = ('iocs',)
    default_batch_size = 64
    default_concurrency = 1

    def describe(self):
        return {**super().describe(), 'labels': {name: 'Syntax match; does not imply maliciousness.' for name in self.cfg.get('labels', [])}}

    async def process_rows(self, job, idxs):
        out = []
        for i in idxs:
            spans = extract_iocs(job.texts[i], self.cfg.get('labels', []))
            out.append({'spans': spans, 'groups': group_entities(spans)})
        return out

    def preview(self, result):
        return result['groups'] if result else None

    def to_columns(self, result):
        return {'iocs': json.dumps([{k: s[k] for k in ('label', 'text', 'normalized')} for s in (result or {}).get('spans', [])], ensure_ascii=False)}

    def matches(self, result, value):
        return bool(result) and value in result['groups']

    def summarize(self, job, results):
        counts = {}
        for result in results:
            for kind, items in (result or {}).get('groups', {}).items():
                counts[kind] = counts.get(kind, 0) + len(items)
        return {'counts': counts}
