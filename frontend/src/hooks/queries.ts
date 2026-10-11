import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, watchJob } from "../api/endpoints";
import { TERMINAL, type JobSnapshot, type RowQuery } from "../api/types";

export const keys = {
  health: ["health"] as const,
  config: ["config"] as const,
  jobs: ["jobs"] as const,
  job: (id: string) => ["job", id] as const,
  summary: (id: string) => ["job", id, "summary"] as const,
  rows: (id: string) => ["job", id, "rows"] as const,
  row: (id: string, idx: number) => ["job", id, "row", idx] as const,
  metrics: (id: string) => ["job", id, "metrics"] as const,
  runs: ["runs"] as const,
  engineMetrics: ["engine-metrics"] as const,
  admin: ["admin", "modules"] as const,
  history: (m?: string) => ["admin", "history", m ?? "*"] as const,
};

export const isTerminal = (s?: JobSnapshot | null) => !!s && TERMINAL.includes(s.status);

/** Fast polling while models load (cold start takes a minute or two), slow once ready. */
export function useHealth() {
  return useQuery({
    queryKey: keys.health,
    queryFn: ({ signal }) => api.health(signal),
    refetchInterval: (q) => (q.state.data?.status === "ready" ? 15_000 : 2_000),
    retry: false,
  });
}

export function useAppConfig() {
  return useQuery({ queryKey: keys.config, queryFn: ({ signal }) => api.config(signal), staleTime: Infinity });
}

export function useJobs() {
  return useQuery({ queryKey: keys.jobs, queryFn: ({ signal }) => api.jobs(signal), refetchInterval: 5_000 });
}

/**
 * A job's snapshot, live. SSE pushes snapshots into the query cache; if the stream drops
 * (proxy restart, laptop sleep) one fetch refreshes the state, then it reconnects.
 */
export function useLiveJob(id: string | null) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: keys.job(id ?? ""),
    queryFn: ({ signal }) => api.job(id!, signal),
    enabled: !!id,
    retry: (n, e) => n < 2 && (e as { status?: number }).status !== 404,
  });
  const [epoch, setEpoch] = useState(0);
  const terminal = isTerminal(query.data);

  useEffect(() => {
    if (!id || !query.data || terminal) return;
    let timer = 0;
    const stop = watchJob(
      id,
      (snap) => qc.setQueryData(keys.job(id), snap),
      () => {
        timer = window.setTimeout(() => {
          qc.invalidateQueries({ queryKey: keys.job(id), exact: true }).finally(() => setEpoch((e) => e + 1));
        }, 1500);
      },
    );
    return () => { stop(); clearTimeout(timer); };
  }, [id, terminal, epoch, qc, !!query.data]); // eslint-disable-line react-hooks/exhaustive-deps

  // When the job stops, everything derived from it is final: refresh once.
  useEffect(() => {
    if (id && terminal) {
      qc.invalidateQueries({ queryKey: keys.summary(id) });
      qc.invalidateQueries({ queryKey: keys.rows(id) });
      qc.invalidateQueries({ queryKey: keys.jobs });
    }
  }, [id, terminal, qc]);

  return query;
}

export function useSummary(job: JobSnapshot | undefined) {
  return useQuery({
    queryKey: keys.summary(job?.id ?? ""),
    queryFn: ({ signal }) => api.summary(job!.id, signal),
    enabled: !!job,
    // Summaries walk every row: poll gently on big jobs.
    refetchInterval: job && !isTerminal(job) ? (job.total > 5_000 ? 5_000 : 2_000) : false,
    placeholderData: keepPreviousData,
  });
}

export function useRows(job: JobSnapshot | undefined, q: RowQuery) {
  // While running, refetch the visible page as rows complete (bucketed, so not on every event).
  const progress = job && !isTerminal(job) ? Math.floor(job.percent / 4) : -1;
  return useQuery({
    queryKey: [...keys.rows(job?.id ?? ""), q, progress],
    queryFn: ({ signal }) => api.rows(job!.id, q, signal),
    enabled: !!job,
    placeholderData: keepPreviousData,
  });
}

export function useRow(jobId: string, idx: number | null, live: boolean) {
  return useQuery({
    queryKey: keys.row(jobId, idx ?? -1),
    queryFn: ({ signal }) => api.row(jobId, idx!, signal),
    enabled: idx !== null,
    refetchInterval: live ? 3_000 : false,
  });
}

/** Timings for the job's performance view: 1 s while running, final once stopped. */
export function useJobMetrics(job: JobSnapshot | undefined) {
  return useQuery({
    queryKey: [...keys.metrics(job?.id ?? ""), job?.status],
    queryFn: ({ signal }) => api.metrics(job!.id, signal),
    enabled: !!job,
    refetchInterval: job && !isTerminal(job) ? 1_000 : false,
    placeholderData: keepPreviousData,
  });
}

export function useRuns() {
  return useQuery({ queryKey: keys.runs, queryFn: ({ signal }) => api.runs(signal), refetchInterval: 10_000 });
}

export function useEngineMetrics() {
  return useQuery({ queryKey: keys.engineMetrics, queryFn: ({ signal }) => api.engineMetrics(signal),
                    refetchInterval: 2_000 });
}
