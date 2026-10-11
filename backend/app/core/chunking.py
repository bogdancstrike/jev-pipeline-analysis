"""Text splitting + probability aggregation for the decision model.

Why this exists: the decider rejects (422) any prompt over the model's per-slot window
instead of truncating it. With the default 8192-token slots a 4k-token document is ONE
forward pass; if you shrink the slots (less VRAM) long documents become chunks whose
answers are aggregated here. No config change needed either way.
"""
import re
from collections.abc import Sequence

_BOUNDARY = re.compile(r"(?<=[.!?…])\s+|\n\s*\n")


def split_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    pieces = [p for p in _BOUNDARY.split(text) if p and p.strip()]
    out: list[str] = []
    buf = ""
    for piece in pieces:
        for part in _hard_wrap(piece.strip(), max_chars):
            candidate = f"{buf} {part}" if buf else part
            if len(candidate) <= max_chars:
                buf = candidate
            else:
                if buf:
                    out.append(buf)
                buf = part
    if buf:
        out.append(buf)
    return out


def _hard_wrap(piece: str, max_chars: int) -> list[str]:
    """A single 'sentence' longer than the budget (tables, scraped junk): cut at spaces."""
    if len(piece) <= max_chars:
        return [piece]
    parts, rest = [], piece
    while len(rest) > max_chars:
        cut = rest.rfind(" ", 0, max_chars)
        cut = cut if cut > max_chars // 2 else max_chars
        parts.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        parts.append(rest)
    return parts


def halve(text: str) -> tuple[str, str]:
    mid = len(text) // 2
    cut = text.rfind(" ", 0, mid)
    if cut < len(text) // 4:
        cut = mid
    return text[:cut].strip(), text[cut:].strip()


def aggregate(weighted: Sequence[tuple[float, dict[str, float]]]) -> tuple[str, float, dict[str, float]]:
    """Weighted mean of per-chunk distributions -> (argmax, its prob, full distribution).

    Mean (not max) on purpose: one off-topic paragraph with a confident spike should not
    flip a document whose other nine chunks agree.
    """
    if not weighted:
        raise ValueError("nothing to aggregate")
    total_w = sum(w for w, _ in weighted) or 1.0
    acc: dict[str, float] = {}
    for w, probs in weighted:
        for k, p in probs.items():
            acc[k] = acc.get(k, 0.0) + w * p
    dist = {k: v / total_w for k, v in acc.items()}
    best = max(dist, key=dist.__getitem__)
    return best, dist[best], dist
