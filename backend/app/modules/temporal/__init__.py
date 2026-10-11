"""Bounded local date normalization. Never guess the anchor of relative dates."""
import asyncio
from datetime import timedelta
import json
import re

import dateparser
from ...core.modules import Kind, Module

_MONTH = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|ianuarie|februarie|martie|aprilie|mai|iunie|iulie|august|septembrie|octombrie|noiembrie|decembrie)'
_WEEKDAY = r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|luni|marți|marti|miercuri|joi|vineri|sâmbătă|sambata|duminică|duminica)'
_DATE = re.compile(rf'\b(?:\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}[./]\d{{1,2}}[./]\d{{4}}|\d{{1,2}}\s+{_MONTH}(?:\s+\d{{4}})?|{_MONTH}\s+\d{{1,2}}(?:,?\s+\d{{4}})?|yesterday|today|tomorrow|ieri|astăzi|astazi|azi|mâine|maine|(?:last|next|this)\s+{_WEEKDAY}|(?:\d+|one|two|three|o|un|două|doua|doi|trei)\s+(?:days?|weeks?|months?|years?)\s+ago|acum\s+(?:\d+|o|un|două|doua|doi|trei)\s+(?:zile?|săptămâni|saptamani|luni|ani))\b', re.I)
_ABSOLUTE_YEAR = re.compile(r'\b\d{4}\b')


def normalize_dates(text, reference=None, languages=None, limit=100):
    base = None
    if reference:
        base = dateparser.parse(str(reference), settings={'STRICT_PARSING': True, 'RETURN_AS_TIMEZONE_AWARE': False})
    out = []
    for match in list(_DATE.finditer(text))[:limit]:
        value = match.group()
        relative = not bool(_ABSOLUTE_YEAR.search(value))
        normalized = None
        if not relative or base:
            settings = {'STRICT_PARSING': not relative, 'RETURN_AS_TIMEZONE_AWARE': False}
            if base:
                settings['RELATIVE_BASE'] = base
            parsed = dateparser.parse(value, languages=languages or ['en', 'ro'], settings=settings)
            weekday = re.fullmatch(r'(last|next|this)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)', value, re.I)
            if weekday and base:
                target = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].index(weekday[2].lower())
                delta = target - base.weekday()
                if weekday[1].lower() == 'last' and delta >= 0:
                    delta -= 7
                elif weekday[1].lower() == 'next' and delta <= 0:
                    delta += 7
                parsed = base + timedelta(days=delta)
            if parsed:
                normalized = parsed.date().isoformat()
        out.append({'text': value, 'start': match.start(), 'end': match.end(), 'normalized': normalized,
                    'status': 'normalized' if normalized else 'missing_reference' if relative and not base else 'unrecognized',
                    'reference': base.date().isoformat() if base else None})
    return out


class TemporalModule(Module):
    name = 'temporal'
    title = 'Temporal normalization'
    description = 'Normalize English/Romanian dates locally; relative dates need publication metadata or a configured reference date.'
    kind = Kind.RECORD
    output_columns = ('temporal',)
    default_batch_size = 32
    default_concurrency = 1

    def describe(self):
        return {**super().describe(), 'records': {'dates': ['text', 'normalized', 'status', 'reference']}}

    async def process_rows(self, job, idxs):
        def work():
            out = []
            for i in idxs:
                reference = self.cfg.get('reference_date') or next((job.df.iloc[i].get(key) for key in ('published_at', 'publication_date', 'date') if str(job.df.iloc[i].get(key, '')).strip()), None)
                dates = normalize_dates(job.texts[i], reference, self.cfg.get('languages'), int(self.cfg.get('max_mentions', 100)))
                out.append({'dates': [{key: {'text': str(date[key]), 'confidence': None} for key in ('text', 'normalized', 'status', 'reference') if date[key] is not None} for date in dates]} if dates else None)
            return out
        return await asyncio.to_thread(work)

    def to_columns(self, result):
        return {'temporal': json.dumps([{k: v['text'] for k, v in d.items()} for d in (result or {}).get('dates', [])], ensure_ascii=False)}

    def preview(self, result):
        if not result:
            return None
        dates = result['dates']
        return {'record': 'dates', 'count': len(dates), 'fields': {k: v['text'] for k, v in dates[0].items()}}

    def matches(self, result, value):
        return any(d.get('status', {}).get('text') == value for d in (result or {}).get('dates', []))

    def summarize(self, job, results):
        counts = {}
        for result in results:
            for date in (result or {}).get('dates', []):
                status = date['status']['text']
                counts[status] = counts.get(status, 0) + 1
        return {'counts': counts}
