"""CSV in (sniffed delimiter, legacy encodings), enriched CSV out (Excel-safe)."""
import csv
import io
from collections.abc import Iterable

import pandas as pd

# OWASP CSV injection: analysts open these files in Excel, and OSINT text is
# attacker-controlled by definition (scraped posts, articles, comments).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
ERROR_MARK = "!error"


class CsvError(ValueError):
    pass


def sniff_delimiter(head: str) -> str:
    """Pick , ; or tab. The header line decides (it is never a multi-line quoted cell, unlike
    article bodies); the stdlib sniffer is only the tie-breaker. pandas' own sniffing parses
    the whole file with its slow Python engine: minutes on a 250 MB upload."""
    counts = {d: head.split("\n", 1)[0].count(d) for d in ",;\t"}
    best = max(counts, key=counts.__getitem__)
    if counts[best] and list(counts.values()).count(counts[best]) == 1:
        return best
    try:
        return csv.Sniffer().sniff(head, delimiters=",;\t").delimiter
    except csv.Error:
        return ","


def parse_csv(data: bytes, max_rows: int, reserved_columns: Iterable[str] = ()) -> pd.DataFrame:
    df = None
    for enc in ("utf-8-sig", "cp1250", "latin-1"):  # cp1250: Romanian/CEE Excel exports
        try:
            head = data[:65536].decode(enc, errors="ignore")
            df = pd.read_csv(
                io.BytesIO(data), dtype=str, keep_default_na=False, encoding=enc,
                sep=sniff_delimiter(head), engine="c",
            )
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:  # pandas raises a zoo of parser errors
            raise CsvError(f"could not parse CSV: {e}") from e
    if df is None:
        raise CsvError("unsupported text encoding")
    cols = {str(c).strip().lower(): c for c in df.columns}
    if "id" not in cols or "text" not in cols:
        raise CsvError(f"CSV needs 'id' and 'text' columns, got {list(df.columns)}")
    df = df.rename(columns={cols["id"]: "id", cols["text"]: "text"})
    if len(df) == 0:
        raise CsvError("CSV has no rows")
    if len(df) > max_rows:
        raise CsvError(f"{len(df)} rows > limit {max_rows}")
    # Re-processing an output file: overwrite our columns, don't duplicate them.
    reserved = set(reserved_columns)
    return df.drop(columns=[c for c in df.columns if c in reserved])


def _escape(v: str) -> str:
    return "'" + v if v and v.startswith(_FORMULA_PREFIXES) else v


def build_output(df: pd.DataFrame, columns: dict[str, list[str]], escape: bool) -> bytes:
    """`columns`: output column -> one string per row, appended after the original columns."""
    out = df.copy()
    for name, values in columns.items():
        out[name] = values
    if escape:
        for c in out.columns:
            out[c] = out[c].map(lambda v: _escape(v) if isinstance(v, str) else v)
    # utf-8-sig so Excel shows diacritics (ș ț ă î â) correctly on double-click
    return out.to_csv(index=False).encode("utf-8-sig")
