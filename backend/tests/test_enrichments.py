from app.modules.ioc import extract_iocs
from app.modules.temporal import normalize_dates
from app.modules.ner.validation import identifiers


def test_iocs_defanged_and_validated_with_original_offsets():
    text = 'Investigate hxxps://example[.]org/path and 192[.]0[.]2[.]1; bad IP 999.1.2.3. Hash ' + 'a' * 64 + '. IPv6 2001:db8::1.'
    out = extract_iocs(text, ['url', 'domain', 'ipv4', 'ipv6', 'sha256'])
    assert {(s['label'], s['normalized']) for s in out} == {('url', 'https://example.org/path'), ('ipv4', '192.0.2.1'), ('sha256', 'a' * 64), ('ipv6', '2001:db8::1')}
    assert all(text[s['start']:s['end']] == s['text'] for s in out)


def test_identifiers_at_sentence_boundaries_and_parenthesized_links():
    text = 'Visit (https://example.org/path). Domain example.org. IP 192.0.2.1. Email analyst@example.org.'
    assert [(s['label'], s['text']) for s in extract_iocs(text, ['url', 'domain', 'ipv4'])] == [
        ('url', 'https://example.org/path'), ('domain', 'example.org'), ('ipv4', '192.0.2.1')]
    assert identifiers(text, {'email'})[0]['text'] == 'analyst@example.org'


def test_relative_dates_require_publication_anchor():
    missing = normalize_dates('Yesterday and last Tuesday, then 2026-10-11.')
    assert [r['normalized'] for r in missing] == [None, None, '2026-10-11']
    assert missing[0]['status'] == 'missing_reference'
    out = normalize_dates('Yesterday, last Tuesday, two weeks ago and 10 October 2026.', '2026-10-11')
    assert [r['normalized'] for r in out] == ['2026-10-10', '2026-10-06', '2026-09-27', '2026-10-10']


def test_romanian_dates_and_unrecognized_invalid_date():
    out = normalize_dates('Ieri, pe 10 octombrie 2026. A urmat 2026-99-99.', '2026-10-11')
    assert [r['normalized'] for r in out] == ['2026-10-10', '2026-10-10', None]
    assert out[-1]['status'] == 'unrecognized'


def test_iban_validation_does_not_label_arbitrary_numbers():
    text = 'RO49 AAAA 1B31 0075 9384 0000 and RO49AAAA1B31007593840001'
    out = identifiers(text, {'iban'})
    assert [s['text'] for s in out] == ['RO49 AAAA 1B31 0075 9384 0000']
