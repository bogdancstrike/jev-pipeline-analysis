# Modules (the 15 analyses)

Each module is a package in `backend/app/modules/<name>/` with its settings in
`config/modules/<name>.yaml`. Settings can be changed at runtime from the **Admin** page
(stored in Postgres, validated before they apply). Speeds are in
[BENCHMARKS.md](BENCHMARKS.md).

| Module | Output columns | Engine (default) | Needs | What it does |
|---|---|---|---|---|
| `language` | language, language_confidence | local CPU (py3langid) | – | ISO 639-1 language from a configured candidate set |
| `category` (Topic) | category, category_confidence | gliner (GLiNER2.5-Decide) | – | One topic from a 30-entry taxonomy |
| `relevance` | relevance, relevance_confidence, relevance_score | laya | – | Relevant to the analyst brief? `score` = P(relevant), for ranking |
| `routing` | routing, routing_confidence | laya | – | Which desk should handle it (or discard) |
| `risk` | risk, risk_confidence, risk_score | laya | – | Ordered risk level; `score` = expected level on [0, 1] |
| `ner` (Entities) | NER (JSON by type) | gliner (gliner2.5-multi) | – | Named entities with character spans |
| `entity_resolution` | entities (JSON) | local CPU | ner | Same entity within and across rows: aliases, acronyms, inflection, Cyrillic transliteration, titles |
| `relations` | relations (JSON triples) | gliner (gliner2.5-multi) | entity_resolution | Directed relations between entities (member_of, leads, works_for, attacks, ...) |
| `fields` (Structured fields) | fields (JSON records) | gliner (gliner2.5-multi) | – | Typed records grounded in the text: what, where, when, actors, casualties, amount |
| `event` (Event type) | event, event_confidence | laya | – | Kind of real-world event reported, or none |
| `event_coreference` (Same event) | event_cluster | laya (yes/no) | event, entity_resolution | Groups rows that report the same event (job-level) |
| `sentiment` | sentiment, sentiment_confidence, sentiment_score | laya | – | Tone; score = P(positive) − P(negative) |
| `intent` | intent, intent_confidence | laya | – | Inform, persuade, mobilize, recruit, incite, threaten, scam, ... |
| `toxicity` | toxicity, toxicity_confidence, toxicity_score | laya | – | Kind of abuse; score = 1 − P(non_toxic) |
| `propaganda` | propaganda, propaganda_confidence, propaganda_techniques | laya | – | Dominant SemEval-2020 technique + every technique above a threshold |

A row that failed in a module gets `!error` in that module's first column; the rest of the row
is still filled.

## How some of them work

**Label modules** (topic, relevance, routing, risk, event, sentiment, intent, toxicity,
propaganda) are configuration on top of one building block (`core/kits/label.py`): an
`instructions` question and a `labels` map of option -> description. They run on any engine:
System One engines answer a choice question; GLiNER2 classifies against the labels and their
descriptions. Long texts are split to the engine's window and per-chunk distributions are
averaged (lead chunk weighted up).

**Entity resolution** is deterministic and explainable (no model): mentions are typed into
groups (person / organization / place / ...), normalized (case, diacritics, Cyrillic
transliteration), mapped through an alias table, and merged by conservative rules (same key;
inflected forms for non-persons; acronyms for organizations; a full name that ends a longer
person mention; a lone surname within one row only). A union-find registry spans the whole
job, so ids are stable across rows.

**Relations** has two strategies, chosen by the engine kind: GLiNER2 extracts directed
(head, relation, tail) spans in one batched pass and they are mapped onto resolved entities;
a System One engine instead asks one question per co-occurring entity pair over their sentence.

**Event coreference** is blocking -> verification -> clustering: rows that report an event and
share resolved entities become candidate pairs (entities present in more than
`max_entity_rows` event rows are too common to block on), each pair is a yes/no question
("same incident, place and time?") and confirmed pairs are union-found into clusters.

## Adding a module

1. Create `backend/app/modules/<name>/module.py` with a `Module` subclass (or a `LabelModule`
   subclass with just `name`, `title`, `description`) and an `__init__.py` exporting it.
2. Add `config/modules/<name>.yaml` (with `engine:` if it needs a model, and a `profile:` with
   its measured speed for the UI).
3. List the class in `CATALOG` in `backend/app/modules/__init__.py`.
4. If its result is a new *kind*, add a renderer to `frontend/src/components/results/registry.tsx`;
   existing kinds (label, entities, resolved, relations, cluster, record) need no UI change.
