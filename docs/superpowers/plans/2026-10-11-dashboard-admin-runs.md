# Dashboard, Admin and Run Management Implementation Plan

> Execute inline in this session; the user has requested implementation.

**Goal:** Make Dashboard and Admin compact and easier to use, and delete selected runs from both history and dashboard statistics.

**Architecture:** Keep the existing React Query / Ant Design UI and FastAPI store abstraction. Delete jobs only after their worker and persistence callback settle, then delete saved records in one store operation. Dashboard run statistics continue to derive from the retained run records; engine counters remain explicitly scoped to backend uptime.

**Tech Stack:** React, TypeScript, Ant Design 6, React Query, FastAPI, PostgreSQL and pytest.

### Task 1: Persistent deletion

Files: `backend/app/core/store.py`, `backend/app/core/pipeline.py`, `backend/app/core/api/routes.py`, `backend/tests/test_api.py`.

- [x] Add `Store.delete_runs(ids: list[str]) -> None` to memory and PostgreSQL stores. PostgreSQL uses parameterized `DELETE FROM runs WHERE id = ANY(%s)`.
- [x] Make `JobManager.delete` asynchronous: cancel active work, await its task including the final save callback, then remove the in-memory job.
- [x] Add `POST /api/runs/delete` with a nonempty list of at most 1000 IDs; deduplicate IDs, delete matching in-memory jobs, delete stored records, return 204. Missing IDs are harmless for safe retries.
- [x] Update existing single-job deletion to also remove persisted history.
- [x] Test finished and history-only deletion, mixed batches, repeated deletion, request validation, and active/queued jobs with no history resurrection.

### Task 2: Runs selection

Files: `frontend/src/api/endpoints.ts`, `frontend/src/pages/RunsPage.tsx`, `frontend/src/hooks/queries.ts`.

- [x] Add `api.deleteRuns(ids)` targeting the new endpoint.
- [x] Add controlled row checkboxes with selection preserved across pagination and clicks isolated from row navigation.
- [x] Put selected count, clear selection, and Delete selected in the table header; confirm deletion and explain active runs stop and statistics update.
- [x] Disable selection during deletion, display request errors, remove successfully deleted query data, invalidate jobs and runs, and evict per-job cached results.
- [x] Refresh saved runs when a live job becomes terminal.

### Task 3: Dashboard layout

Files: `frontend/src/pages/DashboardPage.tsx`, `frontend/src/styles.css`.

- [x] Use a compact status strip for idle activity, and an active run panel with progress, metrics, and a chart only when work exists.
- [x] Keep summary metrics above two independent content columns: recent performance and task throughput on one side, live engine health on the other. Avoid equal-height rows with blank panels.
- [x] Add navigation to New analysis and Runs, meaningful empty states, visible query errors and loading states, and responsive stacking.

### Task 4: Admin layout and editing

Files: `frontend/src/pages/AdminPage.tsx`, `frontend/src/styles.css`.

- [x] Add task search, counts, visible state and engine metadata in a compact navigation panel.
- [x] Group settings, options, JSON, and history in tabs so long JSON/history blocks do not dominate routine edits.
- [x] Arrange settings in a responsive field grid with accessible names and keep Save/Reset adjacent to the task title.
- [x] Protect unsaved changes when switching tasks. Show validation and query errors; label JSON editing and its save action clearly.

### Task 5: Verification

- [x] Run backend tests with fake engines (`pytest -q`) and frontend tests/build (`npm test`, `npm run build`).
- [x] Run Ant Design lint against the changed pages.
- [x] Inspect Dashboard, Admin and Runs in Chromium at desktop/mobile sizes and in dark mode; verify bulk selection, cancellation, deletion, and dashboard refresh against an isolated test backend.
- [x] Review the diff and preserve all pre-existing workspace edits.


## Follow-up implementation completed

- [x] Fumadocs API guide, full-width layout, task selection/input/export/cancellation/retention examples.
- [x] Unified task categories in Admin and New analysis; model guide with measured limits.
- [x] Text & labels task/label/probability table; readable text and selectable entity highlights.
- [x] Searchable Entities, Relations, Fields, Cyber indicators and Temporal normalization views, with source highlighting.
- [x] Same event report excerpts, group filtering and document navigation.
- [x] Extended NER identifiers and numeric validation; selected OSINT tasks, no Qwen fallback for dates.
- [x] Official offline IPTC vocabulary, hierarchical classification, attributed Admin browser and API reference.
- [x] Context/model/prompt/combined-extraction comparisons, held-out event fast-pass evaluation, real 5k/15k/30k four-task workloads.
- [x] Standalone GPU/application production Compose files, shared-key setup, endpoint overrides and deployment guide; local Compose unchanged.
- [x] Unit/API tests, 50k scheduler scale test, browser checks, Compose validation and local rebuild/deployment.

Validation: backend 68 regular tests plus the 50k scale test; frontend 18 tests; Ant Design lint zero issues. Browser checks cover desktop/mobile, source highlighting, taxonomy search, shared navigation and deployed results. Current benchmark details and limitations are recorded in `docs/BENCHMARKS.md`. Private results were backed up before backend replacement.
