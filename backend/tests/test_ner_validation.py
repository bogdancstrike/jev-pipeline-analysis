from app.modules.ner.validation import identifiers, mask_code, validate_spans


def span(text, value, label):
    start = text.index(value)
    return {'start': start, 'end': start + len(value), 'text': value, 'label': label, 'score': .8}


def test_code_mask_preserves_offsets_and_news_names():
    text = 'Maria Popescu met NATO.\n@kafka_handler(\n    name="example", max_workers=16\n)\nasync def process(message):\n    return message\nNATO met Maria Popescu.'
    masked = mask_code(text)
    assert len(masked) == len(text)
    assert masked.startswith('Maria Popescu met NATO.') and masked.endswith('NATO met Maria Popescu.')
    assert 'message' not in masked and 'example' not in masked
    assert [i for i, ch in enumerate(text) if ch == '\n'] == [i for i, ch in enumerate(masked) if ch == '\n']
    assert validate_spans(text, [span(text, 'message', 'person'), span(text, 'Maria Popescu', 'person')]) == [span(text, 'Maria Popescu', 'person')]


def test_money_requires_currency_and_counts_remain_numbers():
    text = 'Processed 100 000 messages at 293.99 records/s. The grant was 50 euros.'
    out = validate_spans(text, [span(text, '100 000', 'money'), span(text, '293.99', 'money'), span(text, '50 euros', 'money')], include_numbers=True)
    assert {(s['text'], s['label']) for s in out} == {('100 000', 'number'), ('293.99', 'number'), ('50 euros', 'money')}
    assert all(text[s['start']:s['end']] == s['text'] for s in out)


def test_identifiers_checksum_and_phone_validation():
    # Publicly documented python-stdnum test fixture; not a real user's data.
    text = 'Email analyst@example.org, phone +40 722 123 456, CNP 1630615123457; wrong 1630615123458. Passport AB1234567.'
    out = identifiers(text, {'email', 'phone', 'cnp', 'personal id'})
    assert {(s['text'], s['label']) for s in out} == {('analyst@example.org', 'email'), ('+40 722 123 456', 'phone'), ('1630615123457', 'cnp'), ('AB1234567', 'personal id')}
    assert all(text[s['start']:s['end']] == s['text'] for s in out)


def test_no_phone_numbers_from_benchmark_counts_ports_or_versions():
    assert identifiers('100,000 messages in 72.34 seconds, Python 3.12.3, localhost:29092, batch_size=32.', {'phone', 'cnp', 'email'}) == []


def test_patterns_override_model_labels_without_duplicate_number_spans():
    text = 'Contact analyst@example.org at +40 722 123 456.'
    out = validate_spans(text, [span(text, 'analyst@example.org', 'organization')], pii={'email', 'phone'}, include_numbers=True)
    assert [s['label'] for s in out] == ['email', 'phone']
