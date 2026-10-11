/** Mirrors backend `core/api/schemas.py` and the module result shapes in `core/modules.py`. */

export type ModuleKind = "label" | "entities" | "resolved" | "relations" | "cluster" | "record";

export interface ModuleInfo {
  name: string;
  title: string;
  description: string;
  kind: ModuleKind;
  scope: "row" | "job";
  requires: string[];
  columns: string[];
  engine: string | null;        // engine name from config/engines.yaml; null = local CPU logic
  engine_kind: "systemone" | "gliner2" | "local";
  default_on: boolean;
  labels?: Record<string, string>;
  review_below?: number;
  records?: Record<string, string[]>;
  dependents?: string[];
  shares_engine_with?: string[];
  profile?: ModuleProfile;
}

/** From each module's YAML `profile:` block, filled from docs/BENCHMARKS.md measurements. */
export interface ModuleProfile {
  speed?: "fast" | "medium" | "slow";
  rows_per_s?: number;     // measured alone (docs/BENCHMARKS.md); drives estimates and the Fast preset
  throughput?: string;     // human sentence for the info point
  notes?: string;
}

export interface SampleInfo {
  file: string;
  rows: number | null;
  bytes: number;
  words_median: number | null;
  languages: string[];
}

export interface AppConfig {
  modules: ModuleInfo[];
  engines: Record<string, { kind: string; description: string }>;
  defaults: string[];
  limits: { max_upload_mb: number; max_rows: number };
  samples: SampleInfo[];
}

export interface EngineStatus {
  name: string;
  kind: "systemone" | "gliner2";
  ready: boolean;
  description: string;
  model?: string;
  device?: string;
  prompt_tps?: number | null;
  vram_reserved_mb?: number | null;
  loaded?: string[];
  degraded?: string | null;   // e.g. a checkpoint fell back to the CPU after a GPU OOM
  modules: string[];
}

export interface Health {
  status: "ready" | "loading" | "degraded";
  degraded?: Record<string, string>;
  engines: Record<string, EngineStatus>;
  modules: Record<string, { ready: boolean; engine: string | null }>;
}

export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled";
export const TERMINAL: JobStatus[] = ["done", "failed", "cancelled"];

export interface JobSnapshot {
  id: string;
  filename: string;
  status: JobStatus;
  error: string | null;
  modules: string[];
  total: number;
  done: number;
  progress: Record<string, { done: number; errors: number }>;
  percent: number;
  failed_rows: number;
  rows_per_s: number;
  eta_s: number | null;
  elapsed_s: number;
  created_at: number;
}

// ------------------------------------------------------------------ module results
export interface LabelResult {
  label: string;
  confidence: number;
  top?: [string, number][];
  score?: number;          // sentiment, toxicity
  toxic?: boolean;         // toxicity
  techniques?: string[];   // propaganda
}

export interface Span { start: number; end: number; text: string; label: string; score: number }
export interface EntitiesResult { spans: Span[]; groups: Record<string, string[]> }

export interface ResolvedEntity {
  id: string; name: string; canonical?: string; label: string; mentions: string[]; spans: [number, number][];
}
export interface ResolvedResult { entities: ResolvedEntity[] }

export interface Relation {
  head: string; head_id?: string; head_label?: string; relation: string;
  tail: string; tail_id?: string; tail_label?: string; confidence: number; evidence?: string;
}
export interface RelationsResult { relations: Relation[]; pairs_checked?: number }

export interface ClusterResult { cluster: string; size: number; peers?: number[]; peer_ids?: string[]; confidence?: number }

// ------------------------------------------------------------------ rows & summary
export interface RowItem {
  idx: number;
  id: string;
  preview: string;
  results: Record<string, unknown>;
  review: string[];
  errors: string[];
}

export interface RowPage { total: number; items: RowItem[] }

export interface RowDetail {
  idx: number;
  id: string;
  text: string;
  results: Record<string, unknown>;
  review: string[];
  errors: Record<string, string>;
}

export interface TopEntity { id: string; name: string; label: string; rows: number; mentions: number }
export interface EventCluster { id: string; size: number; rows: number[]; ids: string[]; event: string | null; title: string }

export interface ModuleSummary {
  counts?: Record<string, number>;
  needs_review?: number;
  errors: number;
  entities?: number;
  top?: TopEntity[];
  clusters?: EventCluster[];
  pairs_checked?: number;
  links?: number;
}

export interface JobSummary {
  modules: Record<string, ModuleSummary>;
  needs_review: number;
}

export interface RowQuery {
  offset: number;
  limit: number;
  filters: [string, string][];
  review: boolean;
  errors: boolean;
  q: string;
}

// ------------------------------------------------------------------ metrics & dashboard
export interface Percentiles { p50: number | null; p95: number | null; p99: number | null; mean: number | null }

export interface ModuleMetrics {
  rows: number; batches: number; start_s: number | null; end_s: number | null;
  wall_s: number; busy_s: number; parallelism: number | null; rows_per_s: number | null;
  batch_ms: Percentiles; row_ms: Percentiles; engine: string | null; errors: number;
}

export interface EngineMetrics {
  kind: string; ready: boolean; requests: number; errors: number; retries: number;
  inflight: number; items: number; latency_ms: Percentiles;
}

export interface JobMetrics {
  job: JobSnapshot;
  wall_s: number;
  rows_per_s: number | null;
  peak_rows_per_s: number;
  modules: Record<string, ModuleMetrics>;
  timeline: { t: number; done: Record<string, number> }[];
  engines: Record<string, EngineMetrics>;
}

export interface RunRecord {
  id: string; filename: string; status: JobStatus; total: number; modules: string[];
  created_at: number; wall_s: number | null; rows_per_s: number | null;
  metrics: { modules: Record<string, ModuleMetrics>; peak_rows_per_s: number; failed_rows: number };
}

// ------------------------------------------------------------------ admin
export interface AdminModule {
  name: string; title: string; description: string; kind: ModuleKind; enabled: boolean;
  requires: string[]; engine_kinds: string[]; engine_choices: string[];
  defaults: Record<string, unknown>; override: Record<string, unknown> | null;
  effective: Record<string, unknown>;
}

export interface HistoryEntry {
  id: number; module: string; action: "update" | "reset";
  before: Record<string, unknown> | null; after: Record<string, unknown> | null;
  changed_at: number; changed_by: string;
}
