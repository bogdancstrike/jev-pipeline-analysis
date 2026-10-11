"""Entity resolution: which mentions, within a row and across the whole job, are the same
real-world entity. Deterministic, explainable, no model:

1. Mentions are typed into *groups* (person / organization / place / ...): only mentions of
   the same group can merge, and labels outside every group (dates, money) are skipped.
2. A mention's key is its normalized form (diacritics folded, case folded, punctuation
   dropped), mapped through the configured alias table (EU = UE = European Union = ...).
3. Merge rules, each cheap and conservative:
   * same key;
   * inflection-tolerant match for non-person groups ("România" ~ "României",
     "Guvernul" ~ "Guvernului"): same token count, every token pair shares a long prefix;
   * acronyms for organizations ("DNSC" ~ "Directoratul Național de Securitate Cibernetică");
   * people: a full name that ends a longer mention is the same person
     ("Finance Minister Andrei Popescu" ~ "Andrei Popescu"), across rows too;
   * Cyrillic is transliterated before matching ("Елена Марін" ~ "Elena Marin"), and
     aliases match inflected forms ("Румунії" ~ alias "Румунія" ~ "Romania");
   * within one row only, a lone surname resolves to the full name mentioned in that row
     ("Popescu" ~ "Andrei Popescu"). Across rows that would merge strangers, so it doesn't.
4. Union-find keeps it incremental: rows can arrive in any order; ids that merge later are
   settled by `settle()` once every row is in.
"""
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

_NON_WORD = re.compile(r"[^\w]+")
_ACRONYM = re.compile(r"^[A-ZĂÂÎȘȚŞŢ]{2,7}$")
_ARTICLES = ("the ",)
# Uk/ru/bg Cyrillic -> Latin, tuned for matching names against their Latin spelling
# (so г -> g: Ukrainian "Галац" is Romanian "Galați"), not for display.
_CYRILLIC = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e", "є": "ie", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h",
    "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e",
    "ю": "iu", "я": "ia", "'": "", "’": "",
})


def normalize(text: str) -> str:
    s = text.casefold().translate(_CYRILLIC)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _NON_WORD.sub(" ", s).strip()
    for a in _ARTICLES:
        if s.startswith(a):
            s = s[len(a):]
    return s


def _token_close(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 4:
        return False
    p = 0
    for x, y in zip(a, b):
        if x != y:
            break
        p += 1
    return p >= 4 and p >= min(len(a), len(b)) - 1


def loose_equal(a: str, b: str) -> bool:
    """Same entity up to inflectional endings: "romania" ~ "romaniei", not "austria" ~ "australia"."""
    ta, tb = a.split(), b.split()
    return len(ta) == len(tb) and all(_token_close(x, y) for x, y in zip(ta, tb))


def _bucket(norm: str) -> tuple[str, int]:
    toks = norm.split()
    return toks[0][:4], len(toks)


@dataclass
class _Node:
    id: str
    group: str
    names: Counter = field(default_factory=Counter)
    labels: Counter = field(default_factory=Counter)
    rows: set = field(default_factory=set)


class EntityRegistry:
    def __init__(self, groups: dict[str, list[str]], aliases: list[list[str]] | None = None,
                 acronym_groups: tuple[str, ...] = ("organization",),
                 stopwords: tuple[str, ...] = (), ignore: tuple[str, ...] = ()):
        self.group_of = {label: g for g, labels in groups.items() for label in labels}
        self.alias: dict[str, str] = {}
        self._alias_index: dict[tuple[str, int], list[str]] = {}
        for names in aliases or []:
            canon = normalize(names[0])
            for n in names:
                self.alias[normalize(n)] = canon
                self._alias_index.setdefault(_bucket(normalize(n)), []).append(normalize(n))
        self.ignore = {normalize(w) for w in ignore}
        self.acronym_groups = set(acronym_groups)
        self.stopwords = {normalize(w) for w in stopwords}
        self._parent: dict[tuple[str, str], tuple[str, str]] = {}
        self._nodes: dict[tuple[str, str], _Node] = {}
        self._loose_index: dict[tuple[str, str, int], set[tuple[str, str]]] = {}
        self._acronyms: dict[tuple[str, str], tuple[str, str]] = {}
        self._by_id: dict[str, tuple[str, str]] = {}
        self._person_suffix: dict[str, set[tuple[str, str]]] = {}
        self._seq = 0

    def _canonical_alias(self, norm: str) -> str:
        if norm in self.alias:
            return self.alias[norm]
        for known in self._alias_index.get(_bucket(norm), ()):
            if loose_equal(norm, known):
                return self.alias[known]
        return norm

    # ---------------------------------------------------------------- union-find
    def _find(self, k: tuple[str, str]) -> tuple[str, str]:
        while self._parent[k] != k:
            self._parent[k] = self._parent[self._parent[k]]
            k = self._parent[k]
        return k

    def _union(self, a: tuple[str, str], b: tuple[str, str]) -> tuple[str, str]:
        ra, rb = self._find(a), self._find(b)
        if ra == rb:
            return ra
        na, nb = self._nodes[ra], self._nodes[rb]
        # The older id survives, so ids already shown to the user stay valid.
        keep, drop = (ra, rb) if int(na.id[4:]) < int(nb.id[4:]) else (rb, ra)
        self._parent[drop] = keep
        k, d = self._nodes[keep], self._nodes[drop]
        k.names.update(d.names)
        k.labels.update(d.labels)
        k.rows |= d.rows
        return keep

    def _node(self, key: tuple[str, str]) -> tuple[str, str]:
        if key not in self._parent:
            self._seq += 1
            self._parent[key] = key
            self._nodes[key] = _Node(id=f"ent_{self._seq}", group=key[0])
            self._by_id[self._nodes[key].id] = key
            group, norm = key
            toks = norm.split()
            if group == "person" and len(toks) >= 2:
                # "finance minister andrei popescu" ~ "andrei popescu": a full name ending another.
                bucket = self._person_suffix.setdefault(" ".join(toks[-2:]), set())
                for other in bucket:
                    o = other[1].split()
                    short, long_ = (toks, o) if len(toks) <= len(o) else (o, toks)
                    if long_[-len(short):] == short:
                        self._union(key, other)
                bucket.add(key)
            elif group != "person" and norm:
                idx = (group, *_bucket(norm))
                for other in self._loose_index.get(idx, ()):
                    if loose_equal(norm, other[1]):
                        self._union(key, other)
                self._loose_index.setdefault(idx, set()).add(key)
        return self._find(key)

    # ---------------------------------------------------------------- acronyms
    def _acronym_of(self, surface: str) -> str | None:
        words = [w for w in re.split(r"[\s\-]+", surface) if w]
        initials = [w[0] for w in words if w[0].isupper() and normalize(w) not in self.stopwords]
        return "".join(initials).upper() if len(initials) >= 2 else None

    def _link_acronyms(self, group: str, surface: str, key: tuple[str, str]) -> None:
        if group not in self.acronym_groups:
            return
        compact = surface.replace(".", "").strip()
        if _ACRONYM.match(compact):
            acr = normalize(compact).upper()
            if (group, acr) in self._acronyms:
                self._union(key, self._acronyms[(group, acr)])
            self._acronyms.setdefault((group, acr), key)
        elif (acr := self._acronym_of(surface)) is not None:
            prior = self._acronyms.get((group, acr))
            if prior is not None:
                self._union(key, prior)
            self._acronyms.setdefault((group, acr), key)

    # ---------------------------------------------------------------- public
    def canonical(self, entity_id: str) -> tuple[str, str] | None:
        """Current (id, name) for an id handed out earlier, after any merges."""
        key = self._by_id.get(entity_id)
        if key is None:
            return None
        root = self._nodes[self._find(key)]
        return root.id, self._name(root)

    @staticmethod
    def _name(node: _Node) -> str:
        """Most frequent surface form. Ties: organizations/places take the longest (the full
        name over the acronym), people the shortest full name (no "Finance Minister")."""
        if not node.names:
            return ""
        if node.group == "person":
            def rank(kv):
                return kv[1], len(kv[0].split()) >= 2, -len(kv[0])
        else:
            def rank(kv):
                return kv[1], len(kv[0])
        return max(node.names.items(), key=rank)[0]

    def resolve_row(self, row: int, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        typed = [(s, self.group_of[s["label"]]) for s in spans if s.get("label") in self.group_of]
        # Within-row surname rule: full person names seen in this row, by last token.
        full_names: dict[str, str] = {}
        for s, g in typed:
            toks = normalize(s["text"]).split()
            if g == "person" and len(toks) >= 2:
                full_names.setdefault(toks[-1], " ".join(toks[-2:]))

        by_root: dict[tuple[str, str], dict[str, Any]] = {}
        for s, g in typed:
            surface = " ".join(s["text"].split())
            norm = normalize(surface)
            if not norm or norm in self.ignore or len(norm) < 2:
                continue
            norm = self._canonical_alias(norm)
            if g == "person" and len(norm.split()) == 1 and norm in full_names:
                norm = full_names[norm]
            key = (g, norm)
            self._node(key)
            self._link_acronyms(g, surface, key)
            root = self._find(key)
            node = self._nodes[root]
            node.names[surface] += 1
            node.labels[s["label"]] += 1
            node.rows.add(row)
            e = by_root.setdefault(root, {"mentions": [], "spans": [], "labels": Counter()})
            if surface not in e["mentions"]:
                e["mentions"].append(surface)
            e["spans"].append([s["start"], s["end"]])
            e["labels"][s["label"]] += 1

        out = []
        for root, e in by_root.items():
            out.append({"id": self._nodes[root].id,
                        "name": max(e["mentions"], key=len),
                        "label": e["labels"].most_common(1)[0][0],
                        "mentions": e["mentions"], "spans": sorted(e["spans"])})
        return sorted(out, key=lambda x: x["spans"][0][0])

    def settle(self, results: list[Any]) -> None:
        """Rewrite per-row results so every id is final and names are canonical."""
        by_id = self._by_id
        for r in results:
            if not r:
                continue
            merged: dict[str, dict[str, Any]] = {}
            for e in r["entities"]:
                root = self._nodes[self._find(by_id[e["id"]])]
                m = merged.get(root.id)
                if m is None:
                    merged[root.id] = {**e, "id": root.id, "canonical": self._name(root)}
                else:  # two ids in this row turned out to be one entity
                    m["mentions"] += [x for x in e["mentions"] if x not in m["mentions"]]
                    m["spans"] = sorted(m["spans"] + e["spans"])
            r["entities"] = sorted(merged.values(), key=lambda x: x["spans"][0][0])

    def top(self, n: int = 20) -> list[dict[str, Any]]:
        roots = {self._find(k) for k in self._nodes}
        nodes = sorted((self._nodes[r] for r in roots), key=lambda x: (-len(x.rows), x.id))
        return [{"id": x.id, "name": self._name(x), "label": x.labels.most_common(1)[0][0],
                 "rows": len(x.rows), "mentions": sum(x.names.values())} for x in nodes[:n]]

    def count(self) -> int:
        return len({self._find(k) for k in self._nodes})
