# Pipeline benchmarks — 11 October 2026

These measurements use the local RTX 3080 (10 GB), real Laya/GLiNER services, the production scheduler, HTTP batching and postprocessing. A task's throughput measured alone is **not** full-pipeline throughput. Synthetic examples help detect regressions; they do not establish production accuracy or a globally optimal model combination.

## Current defaults

| Task family | Default | Reason |
|---|---|---|
| Topic | Laya, 1,500-character lead, 512-token context | 104 records/s alone; 65.7% gold-topic accuracy on the 70 labelled calibration documents. |
| Event type | Laya adaptive first pass: 1,500 chars / 512 tokens; below 0.8 confidence, refine with 3,500 chars / 1,024 tokens | Held-out 400-document test: 62.4/s versus 53.2/s, with 81.2% versus 80.9% event accuracy on 309 labelled documents. |
| Relevance, routing, risk, sentiment, intent, toxicity, propaganda | Laya, 3,500 chars / 1,024 tokens | Blanket 512-token settings changed too many decisions. Propaganda retains a 256-token question budget. |
| Entities, relations, fields | GLiNER multilingual extraction, separate passes | Joint extraction was faster but retained only 51.1% of previous relations; not adopted. Fields use a 2,500-character lead. |
| Language, entity resolution, identifier checks | CPU | No extra model pass. |
| Optional genre / emotion | Laya, 1,500 chars / 512 tokens | Bounded classification, about 90–100 records/s alone. |
| Optional extremist narrative | Laya, 3,500 chars / 1,024 tokens; 128-token question | EN/RO smoke test improved from 20/22 to 21/22; all non-none results require review. |
| Optional cyber indicators / temporal normalization | CPU patterns and validation / dateparser | No model calls. Relative dates require an explicit reference or publication metadata; no Qwen fallback. |
| Optional IPTC | GLiNER Decide language routing, names **and definitions**, up to 5 hierarchy levels | 19/20 correct top-level choices on simple EN/RO smoke examples versus Laya's 17/20. Fine-topic accuracy is unlabelled. |

The original 15 tasks remain selected by default. The six additions (`ioc`, `genre`, `emotion`, `extremism`, `temporal`, `iptc`) are enabled/selectable but `default_on: false`. This avoids increasing existing workloads automatically. There is no automatic switch to Qwen.

## Full pipelines

The comparison uses the same deterministic 100-document sample from `sample-500.csv`, seed `20261011`, with three warm trials. Topic/event gold labels cover 70 of those documents. Runtime includes dependencies and the job-level event matching step, without saving benchmark runs to the dashboard.

| Configuration | Tasks | Median seconds | Records/s | Topic gold | Event gold |
|---|---:|---:|---:|---:|---:|
| Previous configuration | 15 | 44.77 | 2.23 | 54.3% | 90.0% |
| Balanced intermediate settings | 15 | 39.07 | 2.56 | 65.7% | 90.0% |
| Aggressive short-context candidate, rejected as default | 15 | 26.74 | 3.74 | 65.7% | 85.7% |
| **Final defaults** | **15** | **31.43** | **3.18** | **65.7%** | **91.4%** |
| Intermediate settings plus five new tasks, before IPTC | 20 | 37.69 | 2.65 | 65.7% | 90.0% |

The final 15-task run used about 30% less wall time than the previous configuration. These trials occurred at different points in the session; cache state and GPU load contribute to variation. The 20-task result being faster than the intermediate 15-task result is noise/scheduling variation, **not** evidence that extra tasks are free. A separate live 500-document, 20-task run completed in 185.3 s (2.70/s), with zero failed rows.

The aggressive candidate disagreed with the previous risk decisions on 49% of documents and lowered event gold accuracy. Agreement is not accuracy, but such a large unvalidated change is enough to reject it as the default.

## Real 5k, 15k and 30k CSV workloads

All rows were actually processed with **language + topic + cyber indicators + temporal normalization**. Each text is unique; no duplicate-result cache was used. Chunks of 500 allow foreground jobs to finish between chunks. One warm trial per file; waiting for foreground work is reported separately and excluded from processing time.

| CSV size | Processing time | Records/s | Failed rows |
|---|---:|---:|---:|
| 5,000 | 55.86 s | 89.52 | 0 |
| 15,000 | 161.76 s | 92.73 | 0 |
| 30,000 | 316.31 s | 94.84 | 0 |

These are four-task measurements, **not** all-task timings. Median documents are approximately 4,500 characters, and Topic intentionally reads their first 1,500 characters. All 15 default tasks at 3.18/s would take roughly 26 minutes / 79 minutes / 157 minutes respectively; those figures are extrapolations, not measured large-file full-pipeline runs. Actual time depends on text length, entities, selected settings and GPU load.

## Model and context comparisons

100 multilingual synthetic documents, three warm trials per scenario. The small labelled subset is uneven: 46 Romanian and 13 English documents, with only 1–4 labelled documents for several other languages. Topic gold accepts multiple valid labels.

| Topic model/settings | Records/s | Gold topic accuracy |
|---|---:|---:|
| Laya, 1,500 chars / 512 tokens | 104.47 | 65.7% |
| Laya, 3,500 chars / 1,024 tokens | 51.45 | 62.9% |
| GLiNER Decide, 1,500 chars, names only | 46.20 | 54.3% |
| Kev 0.8B, 1,500 chars | 33.56 | 80.0% |
| Kev 0.8B, 3,500 chars | 22.08 | 70.0% |
| Kev 0.8B, full text | 17.91 | 68.6% |

Kev improved topic accuracy on this small corpus but was about three times slower than Laya's fastest topic configuration. The Kev matrix completed all three settings for its first five tasks. The subsequent short-lead sentiment scenario had 52–100 failed rows per trial, followed by 11 timed-out scenarios; those results are excluded from throughput/quality comparisons. It is not a complete Kev comparison. A concurrent Kev deployment exceeded the live 10 GB GPU's memory budget, so Kev remains optional. A CPU attempt failed in its Triton path and is not counted as a quality result. Qwen throughput was not measured in this comparison.

Laya event classification at 512 tokens throughout reached 85.7% on the calibration labels versus 90% at 1,024 tokens. The adaptive candidate was selected on those 100 documents, then checked on the **other 400** documents: 81.2% versus 80.9% on 309 labels and a 17% throughput improvement. These held-out rows still come from the same synthetic template generator. Other tasks had high fallback rates and no clear speed advantage, so adaptive processing is enabled only for Laya Event type.

## Extraction quality and rejected joint pass

A 60-document benchmark with three trials measured separate entity/relation extraction at 6.55 s versus a joint call at 4.34 s (1.51× faster). The joint pass retained 87.1% of previous entity spans and 51.1% of previous relations. Those are agreement figures, not ground truth. The relationship change was too large to adopt.

NER now masks code regions before model extraction, rejects person/organization code identifiers, requires currency evidence for money, and adds local number/identifier extraction with original offsets. In the privately checked technical document, the 13 reported false mentions and 5 false money spans dropped to zero, and 300 general-number spans were recovered. The public artifact contains only aggregates for that private input. Across 30 public news examples, 93.4% of previous exact type/offset spans were retained; changes also include new numeric spans and relabelling. This is not a measured NER accuracy score.

The NER regression workload (36 documents, three warm trials) measured 21.73/s before validation and 23.06/s after it. The small speed difference is within normal variation; the checks add CPU work without another GPU pass.

## Additional task checks

Author-labelled English/Romanian smoke examples cover document genres, expressed emotions, extremist narratives, technical text, news and ordinary political/religious content. They diagnose errors, not representative accuracy.

| Task | Current diagnostic result | Known limit |
|---|---:|---|
| Genre | 6/7 | A short Q&A was classified as a news report. |
| Emotion | 13/13 | Small hand-written set; no production accuracy claim. |
| Extremist narrative | 21/22 with the selected question budget | An ordinary Romanian anger sentence remained a false positive. All non-none results require review. |
| Propaganda | 8/9 at 256 question tokens, versus 6/9 at 192 | Classifier decisions still need contextual review. |
| IPTC, top-level subject | GLiNER 19/20; Laya 17/20 | No labelled fine-topic evaluation. |

Question budgets were compared at 128, 192, 256, 384 and 512 tokens. The selected settings retain more useful propaganda instructions and use a smaller extremist question. Genre and emotion did not improve from increasing that budget.

IPTC pins the [official Media Topics vocabulary](https://www.iptc.org/std/NewsCodes/treeview/mediatopic/mediatopic-en-US.html), version 2026-07-09: 1,085 active topics, 17 roots, attributed under CC BY 4.0. Each branch uses semantic names and definitions, with a broader-topic stop option. On 100 news-length documents, up to five levels measured **15.97 records/s**, median of three trials, zero failed rows. Limiting depth reduces model work at the cost of less specific topics.

Local tasks on the same 100-document sample, three warm trials: Language 4,725/s, Cyber indicators 2,373/s, Temporal normalization 1,106/s. Date-heavy text can cost more than this corpus.

## Backend scale and timing estimates

The 50,000-document scale test uses **instant fake model services** to isolate scheduler, parsing and CPU overhead. It is not a model-throughput result. Current measurement: parse 1.4 s; six-task processing 112.4 s (445 rows/s); summary 0.14 s; snapshot below 1 ms; export 4.5 s (496 MB). The validation work increases CPU cost relative to the earlier 643/s result, while remaining much faster than GPU inference.

The UI estimates use up to five successful runs with at least 20 rows, the same task set, and matching task/engine timing keys. Otherwise they sum measured per-task profiles, including CPU tasks. Incomplete profiles produce an unavailable estimate rather than a misleading partial rate. Saved runs preserve their original module instances/timing keys even if Admin settings later change. Profiles are estimates; they are not a guarantee for every document length or model load.

## Reproduce

Public inputs are `samples/sample-500.csv`, `benchmarks/quality-cases.jsonl` and the pinned baseline/tuning configuration files. Generated large CSVs are reproducible with `scripts/generate_sample.py`; each large-file artifact records the actual file hash. Selected public artifacts under `benchmarks/runs/20261011-*.jsonl` are committed explicitly; private text and private result dumps are not committed.

Run benchmark scripts in a backend one-off to use the same dependencies, Docker networking and secret files as the application. This does not create saved dashboard runs:

```bash
docker compose run --rm --no-deps -T \
  -e PYTHONPATH=/srv:/bench-scripts \
  -v "$PWD/backend/app:/srv/app:ro" \
  -v "$PWD/scripts:/bench-scripts:ro" \
  -v "$PWD/benchmarks:/benchmarks:ro" \
  backend python /bench-scripts/benchmark_models.py --engines laya,gliner --rows 100 --repeats 3
```

Use the same container/mount prefix with:

- `benchmark_pipeline.py --profiles baseline,balanced,speed,extended` for complete pipelines. The current catalog adds IPTC to `extended`; the old 20-task artifact predates IPTC, so its historical timing is not directly reproducible with that newer catalog.
- `benchmark_pipeline.py --profiles final` for the current default 15-task workload.
- `benchmark_adaptive_event.py` for the held-out event comparison.
- `benchmark_large_csv.py` for all rows in the 5k/15k/30k four-task workloads.
- `benchmark_iptc.py` for model/depth/top-level smoke comparisons, and `benchmark_iptc_workload.py` for news-length performance.
- `benchmark_quality.py --tasks genre,emotion,extremism --engines laya --variants lead-1500-512,lead-3500-1024` for diagnostic examples.
- `benchmark_question_budget.py`, `benchmark_gliner_joint.py`, `benchmark_cpu.py` and `benchmark_ner_quality.py` for focused checks. Private NER regression input is optional and must stay outside the repository.

Run on a quiet GPU. The large-file and pipeline scripts wait for active UI jobs at their scheduling boundaries; other focused scripts should be run when the service is idle. Earlier settings/prompt artifacts describe their recorded experiment; re-running against current defaults can change predictions.
