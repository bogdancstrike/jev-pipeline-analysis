# Dashboard, Admin and Run Management Implementation Plan

> Execute inline in this session; the user has requested implementation.

**Goal:** Make Dashboard and Admin compact and easier to use, and delete selected runs from both history and dashboard statistics.

**Architecture:** Keep the existing React Query / Ant Design UI and FastAPI store abstraction. Delete jobs only after their worker and persistence callback settle, then delete saved records in one store operation. Dashboard run statistics continue to derive from the retained run records; engine counters remain explicitly scoped to backend uptime.

**Tech Stack:** React, TypeScript, Ant Design 6, React Query, FastAPI, PostgreSQL and pytest.

### Task 1: Persistent deletion

Files: `backend/app/core/store.py`, `backend/app/core/pipeline.py`, `backend/app/core/api/routes.py`, `backend/tests/test_api.py`.

- [ ] Add `Store.delete_runs(ids: list[str]) -> None` to memory and PostgreSQL stores. PostgreSQL uses parameterized `DELETE FROM runs WHERE id = ANY(%s)`.
- [ ] Make `JobManager.delete` asynchronous: cancel active work, await its task including the final save callback, then remove the in-memory job.
- [ ] Add `POST /api/runs/delete` with a nonempty list of at most 1000 IDs; deduplicate IDs, delete matching in-memory jobs, delete stored records, return 204. Missing IDs are harmless for safe retries.
- [ ] Update existing single-job deletion to also remove persisted history.
- [ ] Test finished and history-only deletion, mixed batches, repeated deletion, request validation, and active/queued jobs with no history resurrection.

### Task 2: Runs selection

Files: `frontend/src/api/endpoints.ts`, `frontend/src/pages/RunsPage.tsx`, `frontend/src/hooks/queries.ts`.

- [ ] Add `api.deleteRuns(ids)` targeting the new endpoint.
- [ ] Add controlled row checkboxes with selection preserved across pagination and clicks isolated from row navigation.
- [ ] Put selected count, clear selection, and Delete selected in the table header; confirm deletion and explain active runs stop and statistics update.
- [ ] Disable selection during deletion, display request errors, remove successfully deleted query data, invalidate jobs and runs, and evict per-job cached results.
- [ ] Refresh saved runs when a live job becomes terminal.

### Task 3: Dashboard layout

Files: `frontend/src/pages/DashboardPage.tsx`, `frontend/src/styles.css`.

- [ ] Use a compact status strip for idle activity, and an active run panel with progress, metrics, and a chart only when work exists.
- [ ] Keep summary metrics above two independent content columns: recent performance and task throughput on one side, live engine health on the other. Avoid equal-height rows with blank panels.
- [ ] Add navigation to New analysis and Runs, meaningful empty states, visible query errors and loading states, and responsive stacking.

### Task 4: Admin layout and editing

Files: `frontend/src/pages/AdminPage.tsx`, `frontend/src/styles.css`.

- [ ] Add task search, counts, visible state and engine metadata in a compact navigation panel.
- [ ] Group settings, options, JSON, and history in tabs so long JSON/history blocks do not dominate routine edits.
- [ ] Arrange settings in a responsive field grid with accessible names and keep Save/Reset adjacent to the task title.
- [ ] Protect unsaved changes when switching tasks. Show validation and query errors; label JSON editing and its save action clearly.

### Task 5: Verification

- [ ] Run backend tests with fake engines (`pytest -q`) and frontend tests/build (`npm test`, `npm run build`).
- [ ] Run Ant Design lint against the changed pages.
- [ ] Inspect Dashboard, Admin and Runs in Chromium at desktop/mobile sizes and in dark mode; verify bulk selection, cancellation, deletion, and dashboard refresh against an isolated test backend.
- [ ] Review the diff and preserve all pre-existing workspace edits.
