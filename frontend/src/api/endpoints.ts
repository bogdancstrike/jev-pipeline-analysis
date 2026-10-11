import { ApiError, request } from "./client";
import type {
  AdminModule, AppConfig, EngineMetrics, Health, HistoryEntry, JobMetrics, JobSnapshot, JobSummary, RowDetail,
  RowPage, RowQuery, RunRecord,
} from "./types";

const json = (body: unknown) => ({ headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  health: (signal?: AbortSignal) => request<Health>("/health", { signal }),
  config: (signal?: AbortSignal) => request<AppConfig>("/config", { signal }),
  jobs: (signal?: AbortSignal) => request<JobSnapshot[]>("/jobs", { signal }),
  job: (id: string, signal?: AbortSignal) => request<JobSnapshot>(`/jobs/${id}`, { signal }),
  summary: (id: string, signal?: AbortSignal) => request<JobSummary>(`/jobs/${id}/summary`, { signal }),
  cancel: (id: string) => request<JobSnapshot>(`/jobs/${id}/cancel`, { method: "POST" }),
  remove: (id: string) => request<void>(`/jobs/${id}`, { method: "DELETE" }),
  rows: (id: string, q: RowQuery, signal?: AbortSignal) =>
    request<RowPage>(`/jobs/${id}/rows`, {
      signal,
      params: { offset: q.offset, limit: q.limit, q: q.q.trim(), review: q.review, errors: q.errors,
                f: q.filters.map(([m, v]) => `${m}:${v}`) },
    }),
  row: (id: string, idx: number, signal?: AbortSignal) => request<RowDetail>(`/jobs/${id}/rows/${idx}`, { signal }),
  resultUrl: (id: string) => `/api/jobs/${id}/result.csv`,

  metrics: (id: string, signal?: AbortSignal) => request<JobMetrics>(`/jobs/${id}/metrics`, { signal }),
  engineMetrics: (signal?: AbortSignal) => request<Record<string, EngineMetrics>>("/engines/metrics", { signal }),
  runs: (signal?: AbortSignal) => request<RunRecord[]>("/runs", { signal, params: { limit: 200 } }),

  /** Start a job on a sample the server already has: nothing is uploaded. */
  sampleJob: (sample: string, modules: string[]) =>
    request<JobSnapshot>("/jobs/sample", { method: "POST", ...json({ sample, modules }) }),
  /** Start a job on pasted text, one article per item. */
  textJob: (texts: string[], modules: string[]) =>
    request<JobSnapshot>("/jobs/text", { method: "POST", ...json({ texts, modules }) }),

  admin: {
    modules: (signal?: AbortSignal) => request<AdminModule[]>("/admin/modules", { signal }),
    save: (name: string, config: Record<string, unknown>) =>
      request<AdminModule>(`/admin/modules/${name}`, { method: "PUT", ...json({ config, changed_by: "admin-ui" }) }),
    reset: (name: string) => request<AdminModule>(`/admin/modules/${name}`, { method: "DELETE" }),
    history: (module?: string, signal?: AbortSignal) =>
      request<HistoryEntry[]>("/admin/history", { signal, params: { module, limit: 50 } }),
    engines: (signal?: AbortSignal) =>
      request<{ store: string; engines: Record<string, Record<string, unknown>> }>("/admin/engines", { signal }),
  },

  /** XHR rather than fetch: fetch still has no upload progress events. */
  createJob(file: File, modules: string[], onProgress: (pct: number) => void): Promise<JobSnapshot> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const form = new FormData();
      form.append("file", file);
      form.append("modules", modules.join(","));
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
      xhr.onload = () => {
        let body: { error?: string; message?: string; details?: Record<string, unknown> } = {};
        try { body = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body as unknown as JobSnapshot);
        else reject(new ApiError(xhr.status, body.error ?? "upload", body.message ?? `Upload failed (${xhr.status})`,
                                 body.details ?? {}, xhr.getResponseHeader("x-request-id")));
      };
      xhr.onerror = () => reject(new ApiError(0, "network", "Network error while uploading.", {}, null));
      xhr.open("POST", "/api/jobs");
      xhr.send(form);
    });
  },
};

/** Server-Sent Events for one job; closes itself on a terminal status. */
export function watchJob(id: string, onSnapshot: (s: JobSnapshot) => void, onDrop: () => void): () => void {
  const es = new EventSource(`/api/jobs/${id}/events`);
  es.onmessage = (e) => {
    const snap = JSON.parse(e.data) as JobSnapshot;
    onSnapshot(snap);
    if (["done", "failed", "cancelled"].includes(snap.status)) es.close();
  };
  es.onerror = () => { es.close(); onDrop(); };
  return () => es.close();
}
