"""Entity spans -> the grouped, de-duplicated shape written to the CSV."""


def group_entities(spans: list[dict]) -> dict[str, list[str]]:
    """CSV-friendly shape: {label: [unique surface forms, best score first]}."""
    best: dict[tuple[str, str], tuple[float, str]] = {}
    for e in spans:
        key = (e["label"], " ".join(e["text"].split()).casefold())
        if key not in best or e["score"] > best[key][0]:
            best[key] = (e["score"], " ".join(e["text"].split()))
    grouped: dict[str, list[tuple[float, str]]] = {}
    for (label, _), (score, surface) in best.items():
        grouped.setdefault(label, []).append((score, surface))
    return {lbl: [s for _, s in sorted(v, reverse=True)] for lbl, v in sorted(grouped.items())}
