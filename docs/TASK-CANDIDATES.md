# Additional NLP tasks for OSINT

This is the final numbered list discussed with the user. Only **9, 13, 14, 15 and 17**
are approved and implemented. Extended NER identifiers were separately approved and are
part of Entities. The other recommendations remain proposals.

Performance means incremental work per document, not full-pipeline throughput.
Short Laya classification measured roughly 50–110 records/s alone on this RTX 3080.
Generation, embeddings and new extraction schemas need their own benchmarks.

| # | Task | OSINT value | Performance impact | Model choice and reason |
|---|---|---|---|---|
| 1 | Translation | Read foreign-language reports in a common analyst language. | High for generation; run on demand and cache. | Evaluate a dedicated multilingual translation model; Qwen for difficult passages if its translation quality justifies the time. |
| 2 | Summarization | Produce a short overview with source evidence. | Low for extractive sentence selection; high for generated summaries. | CPU extractive baseline for speed; Qwen on demand for fluent summaries. |
| 3 | Keyphrase extraction | Find concepts that proper-name NER misses. | Low CPU baseline or one extraction pass. | YAKE baseline; GLiNER for domain-specific phrase spans. |
| 4 | Claim extraction | Identify explicit assertions with attribution for verification. | Medium to high; cap claims per document. | GLiNER structured extraction for bounded claims; evaluate Qwen for complex assertions. |
| 5 | Fact / opinion classification | Separate factual presentation, opinion and attributed allegations. | One short pass per document or selected sentence. | Laya for fast closed-label classification; preserve evidence rather than presenting a truth verdict. |
| 6 | Target-conditioned stance | Identify support or opposition toward an actor or policy. | One pass per target; cap target count. | Laya for high-volume classification using target-local context. |
| 7 | Textual entailment / contradiction | Compare conflicting claims from related reports. | One pass per candidate pair; all-pairs comparison is expensive. | Evaluate Kev for closed-label reasoning; keep it only if measured gains justify its slower serving and memory cost. |
| 8 | Quote and speaker extraction | Distinguish a speaker's words from a journalist's reporting. | Boundary parsing is cheap; ambiguous attribution adds extraction work. | GLiNER with quote and speaker fields, assisted by deterministic quotation boundaries. |
| **9** | **Temporal normalization** | Turn explicit and relative dates into sortable calendar dates. | **Local CPU parsing; no model calls.** | **dateparser + bounded patterns; publication date or explicit reference required for relative dates. No Qwen fallback.** |
| 10 | Geoparsing | Resolve mentioned places to stable IDs and coordinates. | Low for indexed gazetteer lookup; optional disambiguation pass. | Offline gazetteer first; Laya for a small set of ambiguous candidates. |
| 11 | Pronoun coreference | Link “he”, “she” and “the company” to named actors. | Medium to high, especially across long documents. | Evaluate a dedicated coreference model first; Qwen for difficult cases on demand. |
| 12 | Extractive question answering | Answer analyst questions with an exact supporting passage. | Per-question cost; restrict retrieved context. | Evaluate a dedicated multilingual extractive QA model; Qwen when constrained extraction requires reasoning. |
| **13** | **Cyber indicator extraction** | Find URLs, domains, IPv4/IPv6 addresses and file hashes. | **Very low CPU cost, no model pass.** | **Patterns + ipaddress validation and defang normalization. A match does not establish maliciousness.** |
| **14** | **Document genre classification** | Separate news, opinion, interviews, press releases and technical documentation. | **One short classification pass.** | **Laya with a 1,500-character lead and 512-token context: fast and suited to a fixed label set.** |
| **15** | **Emotion classification** | Identify expressed anger, fear, joy and other emotions separately from sentiment. | **One short classification pass.** | **Laya; instructions distinguish the author's emotion from a sad or frightening reported event.** |
| 16 | Hate-target extraction | Identify the target of hostile language with evidence spans. | Additional extraction schema/pass. | GLiNER for exact target spans; evaluate a classifier for contextual interpretation. |
| **17** | **Extremist narrative classification** | Distinguish explicit violent-extremist endorsement, condemnation and neutral reporting. | **Short classification; explicit subject screening may add a pass.** | **Laya with domain-specific options and review flags. Ordinary political or religious content must remain separate.** |
| 18 | ATT&CK technique classification | Map cyber reports to a controlled technique vocabulary. | Medium; hierarchical candidate filtering avoids a huge schema. | Laya for candidate classification using an offline ATT&CK taxonomy; verify supporting evidence. |
| 19 | Uncertainty / speculation detection | Flag hedging, rumours and conditional claims. | One short pass, or multiple passes for sentence-level coverage. | Laya for a small label set with retained source sentences. |
| 20 | Cross-language semantic similarity | Retrieve related reports despite wording and language differences. | One embedding pass plus indexed search. | Evaluate BGE-M3 for multilingual retrieval; threshold tuning is needed to distinguish same topic from same event. |

The five new modules are enabled and selectable, with `default_on: false`, so adding
features does not silently increase the cost of existing default analyses. “All tasks”
includes them. API names are `temporal`, `ioc`, `genre`, `emotion` and `extremism`.
