# Engines and configuration: choosing the model for each task

Two files decide which model does what:

* **`config/engines.yaml`**: the models that exist (URL, key, limits, batching). Infrastructure.
* **`config/modules/<task>.yaml`**: what a task asks and **which engine** it uses (`engine: laya`).
  The Admin page edits these at runtime (overrides stored in Postgres).

To move a task to another model: change its `engine:` (YAML or Admin page). To add a model:
add an entry to `engines.yaml` and a service to `docker-compose.yml`.

## Default assignment

| Model family | Engine | Tasks |
|---|---|---|
| **GLiNER2.5** (Fastino, Apache-2.0): `GLiNER2.5-Decide` 340M (EN), `GLiNER2.5-multi-Decide` 287M, `gliner2.5-multi-v1` | `gliner` | named entities, relations, structured fields, taxonomy (topic) |
| **Laya** (Convai Innovations, Apache-2.0): 421M English + 322M multilingual (100+ languages) | `laya` | relevance, risk, routing, sentiment, event type, intent, toxicity, propaganda, same-event verification |
| Kev 0.8B (Apache-2.0), optional | `kev` | none by default; any label task can switch to it |
| Qwen3-4B AWQ on vLLM, optional | `qwen` | none by default; any label task can switch to it |
| py3langid (BSD) | – (local) | language |

Why: GLiNER2.5 is an encoder that reads spans, so it is the right tool for extraction
(entities, relation spans, typed fields) and fast zero-shot classification. Laya returns
calibrated probabilities for closed questions in 100+ languages, which is what relevance,
risk, routing and the tone categories are.

**GLiNER2.5-Decide is English-only.** The `gliner` engine routes per text: English to
`GLiNER2.5-Decide`, everything else to `GLiNER2.5-multi-Decide`
(`model: {en: decide, "*": decide-multi}`). The Decide checkpoints are classification
specialists; extraction tasks pin the general checkpoint with `engine_options: {model: extract-multi}`
(measured: Decide returns no relations, `gliner2.5-multi-v1` does).

## `engines.yaml` reference

```yaml
engines:
  laya:
    kind: systemone              # or gliner2
    url: http://laya:8000        # or urls: [a, b] for round-robin replicas
    api_key_secret: laya_api_key # file in /run/secrets (secrets-init creates it)
    ready_path: /health          # readiness probe
    models_path: null            # GET that publishes limits (the decider has one); null = use `limits`
    limits: {max_sequence_tokens: 2048, max_question_tokens: 512}
    chars_per_token: 3.2         # to pre-split long texts to the window
    request: {max_len: 2048}     # extra fields sent with every request
    batch: {path: /v1/systemone/batch, max_states: 32}   # many documents per request
    concurrency: 4               # requests in flight
  gliner:
    kind: gliner2
    url: http://extractor:8080
    model: {en: decide, "*": decide-multi}   # alias, or per-language route
    threshold: 0.5
    chunk_size: 384              # words per window for long documents
    chunk_overlap: 64
    batch_size: 16               # texts per forward pass inside the service
```

A task can override engine options per call: `engine_options: {model: extract-multi, threshold: 0.3}`.

## Swapping examples

* Topic on Laya instead of GLiNER: `config/modules/category.yaml` -> `engine: laya`.
* Sentiment on Kev: start Kev (`docker compose --profile kev up -d kev`), then `engine: kev`.
* All tone tasks on the Qwen decider: `docker compose --profile qwen up -d llm decider`, then
  `engine: qwen` in each.
* A different GLiNER checkpoint: build the extractor with
  `--build-arg EXTRACTOR_MODELS='{"decide":"...","extract-multi":"..."}'` and keep the aliases.

## Extractor tuning (environment)

| Variable | Default | Effect |
|---|---|---|
| `EXTRACTOR_GPU_MEM_FRACTION` | 0.5 | Hard VRAM cap for the extractor process |
| `EXTRACTOR_DTYPE` | bfloat16 | Weights dtype on GPU (fp32 on CPU) |
| `EXTRACTOR_LOAD_OPTIONS` | `{}` | gliner2 load options, e.g. `{"attention_backend": "disentangled_flash"}` |

On CUDA OOM the extractor halves the batch and remembers the size that fit per
(checkpoint, task), so a long-document spike costs one retry, not one per request.

## Laya tuning (environment)

| Variable | Value | Why |
|---|---|---|
| `LAYA_MODELS` | english,multilingual | preloaded checkpoints, routed per request language |
| `LAYA_MAX_TOKEN_BUDGET` | 4096 | cap on per-request `max_len` |
| `LAYA_MAX_BATCH_TOKENS` | 32768 | bounds one forward pass; without it the allocator kept 6.5 GB |
| `LAYA_MAX_CONCURRENT` | 32 | admission limit; excess gets 503 + retry-after |
