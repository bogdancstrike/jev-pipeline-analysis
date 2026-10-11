"""Cheap span validation and deterministic identifiers; offsets always refer to original text."""
import re

import phonenumbers
from stdnum import iban
from stdnum.ro import cnp

_EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+(?![\w-]|\.\w)")
_CNP = re.compile(r"(?<!\d)[1-9]\d{12}(?!\d)")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]){11,30}\b")
_PERSONAL_ID = re.compile(r"(?i)\b(?:personal\s+id|identity\s+(?:number|card)|passport(?:\s+(?:number|no\.?))?|pașaport|pasaport|carte\s+de\s+identitate|seria\s+(?:ci|buletin))\s*(?:[:#=]|no\.?|nr\.?)?\s*([A-Z]{1,3}[ -]?\d{5,9}|\d{6,10})\b")
_CURRENCY = re.compile(r"(?i)(?:[$€£¥₽₴₹₺]|\b(?:USD|EUR|RON|GBP|JPY|CHF|CAD|AUD|CNY|RUB|UAH|INR|dollars?|euros?|lei|leu|pounds?|rubles?|roubles?|hryvni?as?|yen|yuan|dolari|lire)\b)")
_NUMBER = re.compile(r"(?<![\w])[-+]?\d+(?:[ ,\u00a0\u202f.]\d{3})*(?:[.,]\d+)?(?:\s?%)?(?![\w])")
_CODE = re.compile(r"^\s*(?:from\s+\w[\w.]*\s+import\b|import\s+\w|(?:async\s+)?def\s+\w+\s*\(|class\s+\w+|return\b|@\w+|(?:[\w.]+\s*=\s*)|[{}\[\]]\s*[,;]?\s*$|[\"'][\w-]+[\"']\s*:|(?:curl|pip|python3?|uvicorn|git|docker|source|cp|printf)\s)")


def code_ranges(text: str) -> list[tuple[int, int]]:
    """Recognize fenced blocks and explicit code lines, not ordinary indented prose."""
    ranges, offset, fenced, continuation = [], 0, False, 0
    for line in text.splitlines(keepends=True):
        fence = line.lstrip().startswith(('```', '~~~'))
        is_code = fenced or fence or bool(_CODE.match(line)) or continuation > 0
        if is_code:
            ranges.append((offset, offset + len(line)))
            # Continuations cover multi-line calls, dictionaries and decorators.
            continuation = max(0, continuation + line.count('(') + line.count('[') + line.count('{') - line.count(')') - line.count(']') - line.count('}'))
        else:
            continuation = 0
        if fence:
            fenced = not fenced
        offset += len(line)
    return ranges


def mask_code(text: str) -> str:
    chars = list(text)
    for start, end in code_ranges(text):
        chars[start:end] = ['\n' if ch == '\n' else ' ' for ch in chars[start:end]]
    return ''.join(chars)


def identifiers(text: str, enabled: set[str], region: str = "RO") -> list[dict]:
    spans = []

    def add(start, end, label, validation):
        if not any(a['start'] < end and start < a['end'] for a in spans):
            spans.append({'start': start, 'end': end, 'text': text[start:end], 'label': label,
                          'score': 1.0, 'source': 'pattern', 'validation': validation})

    if 'email' in enabled:
        for match in _EMAIL.finditer(text):
            add(*match.span(), 'email', 'syntax')
    if 'cnp' in enabled:
        for match in _CNP.finditer(text):
            if cnp.is_valid(match.group()):
                add(*match.span(), 'cnp', 'checksum_date_region')
    if 'iban' in enabled:
        for match in _IBAN.finditer(text):
            if iban.is_valid(match.group()):
                add(*match.span(), 'iban', 'checksum')
    if 'personal id' in enabled:
        for match in _PERSONAL_ID.finditer(text):
            add(*match.span(1), 'personal id', 'labelled_format')
    if 'phone' in enabled:
        for match in phonenumbers.PhoneNumberMatcher(text, region, leniency=phonenumbers.Leniency.VALID):
            add(match.start, match.end, 'phone', 'numbering_plan')
    return sorted(spans, key=lambda span: (span['start'], span['end']))


def validate_spans(text: str, spans: list[dict], *, exclude_code: bool = True, money_currency: bool = True,
                   pii: set[str] | None = None, include_numbers: bool = False, region: str = "RO") -> list[dict]:
    ranges = code_ranges(text) if exclude_code else []
    out = []
    for span in spans:
        start, end = span['start'], span['end']
        if not 0 <= start < end <= len(text) or text[start:end] != span['text']:
            continue
        if any(a < end and start < b for a, b in ranges):
            continue
        if span['label'] in {'person', 'organization', 'company'} and re.fullmatch(r'[a-z]\w*_\w+', span['text']):
            continue
        if money_currency and span['label'] == 'money':
            # Currency may sit just outside the model's amount span; stay on this line.
            nearby = text[max(text.rfind('\n', 0, start) + 1, start - 12):min(len(text), end + 18)].split('\n', 1)[0]
            if not _CURRENCY.search(nearby):
                continue
        out.append(span)
    # Deterministic identifiers take priority over ambiguous model spans at the same offsets.
    for span in identifiers(text, pii or set(), region):
        out = [old for old in out if not (old['start'] < span['end'] and span['start'] < old['end'])]
        out.append(span)
    if include_numbers:
        for match in _NUMBER.finditer(text):
            start, end = match.span()
            if not any(old['start'] < end and start < old['end'] for old in out):
                out.append({'start': start, 'end': end, 'text': match.group(), 'label': 'number',
                            'score': 1.0, 'source': 'pattern', 'validation': 'numeric_syntax'})
    return sorted(out, key=lambda span: (span['start'], -span['end']))
