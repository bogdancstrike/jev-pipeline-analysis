"""Pure core logic: chunking, aggregation, CSV in/out."""
import pandas as pd

from app.core.chunking import aggregate, split_text
from app.core.csv_io import build_output, parse_csv


def test_split_respects_budget_and_keeps_text():
    text = " ".join(f"Sentence number {i} talks about the budget." for i in range(200))
    chunks = split_text(text, 300)
    assert all(len(c) <= 300 for c in chunks)
    assert " ".join(chunks).split() == text.split()


def test_aggregate_mean_not_max():
    cat, conf, _ = aggregate([(1, {"a": 0.9, "b": 0.1}), (1, {"a": 0.3, "b": 0.7}), (1, {"a": 0.2, "b": 0.8})])
    assert cat == "b" and round(conf, 3) == 0.533


def test_csv_semicolon_cp1250_and_formula_escape():
    # Legacy Windows exports use cedilla forms (ş ţ); cp1250 cannot encode comma-below (ș ț).
    raw = "id;text\n1;=HYPERLINK(\"http://evil\")\n2;Şedinţa Guvernului de la Bucureşti\n".encode("cp1250")
    df = parse_csv(raw, 100)
    out = build_output(df, {"category": ["a", "b"]}, escape=True).decode("utf-8-sig")
    assert "'=HYPERLINK" in out and "Şedinţa Guvernului de la Bucureşti" in out


def test_reprocessing_an_output_file_drops_our_columns():
    raw = b"id,text,category,sentiment\n1,hello,x,y\n"
    df = parse_csv(raw, 10, reserved_columns=["category", "sentiment"])
    assert list(df.columns) == ["id", "text"]


def test_csv_without_text_column_is_rejected():
    import pytest

    from app.core.csv_io import CsvError
    with pytest.raises(CsvError, match="'id' and 'text'"):
        parse_csv(b"id,body\n1,x\n", 10)


def test_build_output_keeps_original_columns_first():
    df = pd.DataFrame({"id": ["1"], "text": ["t"], "source": ["s"]})
    out = build_output(df, {"language": ["ro"]}, escape=False).decode("utf-8-sig")
    assert out.splitlines()[0] == "id,text,source,language"
