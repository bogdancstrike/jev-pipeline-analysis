# Text triage — on-prem text enrichment pipeline

Upload a CSV (or paste articles, or pick a built-in sample) and get every row enriched by up to
15 analyses, on one machine with one GPU, with no network access at runtime:

language · topic · relevance · routing · risk · entities · entity resolution · relations ·
structured fields · event type · same-event clustering · sentiment · intent · toxicity · propaganda

```bash
python3 scripts/generate_sample.py   # sample datasets (50 … 50,000 articles); small ones are in git
docker compose up --build -d         # first build downloads the model weights into the images
open http://localhost:8088
```

Prerequisites: NVIDIA driver ≥ 570, Docker with Compose and the NVIDIA Container Toolkit.

## Models (all Apache-2.0, run locally)

| Family | Tasks |
|---|---|
| **GLiNER2.5** (Fastino): GLiNER2.5-Decide 340M (EN) / multi-Decide 287M, gliner2.5-multi-v1 | entities, relations, structured fields, topic |
| **Laya** (Convai Innovations): 421M EN + 322M multilingual | relevance, risk, routing, sentiment, event type, intent, toxicity, propaganda, same-event check |
| Kev 0.8B, Qwen3-4B on vLLM | optional engines (`--profile kev`, `--profile qwen`) |

Which model runs which task is configuration (`engine:` in `config/modules/<task>.yaml`, or the
Admin page); see [docs/ENGINES.md](docs/ENGINES.md).

## UI

New analysis (presets All / Fast / Topic only / None, info point per task, run-time estimate) ·
Runs (live counter, Overview, Performance charts, Rows with a per-row drawer and relation graph) ·
Dashboard · Admin (edit task options/prompts/thresholds/engine; stored in PostgreSQL).

## Docs

* [ARCHITECTURE.md](docs/ARCHITECTURE.md) — services, the modulith backend, scheduling, security
* [MODULES.md](docs/MODULES.md) — the 15 analyses, outputs, adding a module
* [ENGINES.md](docs/ENGINES.md) — models, `engines.yaml`, swapping a model for a task, tuning
* [BENCHMARKS.md](docs/BENCHMARKS.md) — measured speed and accuracy on the RTX 3080

## Development

```bash
(cd backend && pip install -r requirements.txt pytest pytest-asyncio && pytest -q)   # 34 tests
(cd backend && pytest -m scale -s)        # 50k-row scale test (needs samples/sample.csv)
(cd decider && pytest -q)
(cd frontend && npm install && npm test && VITE_API_TARGET=http://localhost:8088 npm run dev)
python3 scripts/benchmark.py --sample sample-500.csv --each   # benchmark the running stack
```

### Production on two servers

Use `docker-compose.gpu.yml` on the GPU/model host and `docker-compose.app.yml` on the frontend/backend/database host. The existing local Compose remains unchanged. See [the two-server deployment guide](docs/DEPLOYMENT.md) for private endpoint configuration, shared model keys, optional engines and update commands.
