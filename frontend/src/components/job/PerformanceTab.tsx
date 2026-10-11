import { Card, Skeleton, Table } from "antd";

import type { JobSnapshot, ModuleInfo } from "../../api/types";
import { isTerminal, useJobMetrics } from "../../hooks/queries";
import { duration, num } from "../../lib/format";
import { ChartCard } from "../charts/ChartCard";
import { LineChart } from "../charts/LineChart";
import { OutcomeBars } from "../charts/OutcomeBars";
import { Timeline } from "../charts/Timeline";
import { ErrorAlert } from "../common/ErrorAlert";

const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat-tile">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

/** Where the time went: throughput over time, each task's window, outcomes, engine latency. */
export function PerformanceTab({ job, modules }: { job: JobSnapshot; modules: ModuleInfo[] }) {
  const q = useJobMetrics(job);
  const m = q.data;
  if (q.error && !m) return <ErrorAlert error={q.error} onRetry={() => q.refetch()} />;
  if (!m) return <Skeleton active />;

  const info = Object.fromEntries(modules.map((x) => [x.name, x]));
  const rowScoped = job.modules.filter((n) => info[n]?.scope !== "job");
  // Records fully processed by every row-level task, over time; and its 1 s rate.
  const done = m.timeline.map((p) => ({ x: p.t, y: Math.min(...rowScoped.map((n) => p.done[n] ?? 0)) }));
  // Rate over a trailing window that grows with the run (rows finish in batches, so a short
  // window turns into a sawtooth of batch arrivals rather than a throughput).
  const k = Math.max(3, Math.round(done.length / 12));
  const smooth = done.slice(1).map((p, i) => {
    const a = done[Math.max(0, i + 1 - k)];
    return { x: p.x, y: Math.round((Math.max(0, p.y - a.y) / Math.max(0.001, p.x - a.x)) * 10) / 10 };
  });

  // Colour = engine identity, slots assigned in a fixed order (never by rank).
  const engines = [...new Set(job.modules.map((n) => m.modules[n]?.engine ?? "local CPU"))].sort();
  const colorOf = (e: string) => SERIES[engines.indexOf(e) % SERIES.length];
  const spans = job.modules.filter((n) => m.modules[n]?.start_s != null).map((n) => {
    const mm = m.modules[n];
    const engine = mm.engine ?? "local CPU";
    return { key: n, label: info[n]?.title ?? n, start: mm.start_s ?? 0, end: mm.end_s ?? mm.start_s ?? 0, group: engine,
             color: colorOf(engine),
             detail: `${engine} · ${num(mm.rows)} rows in ${mm.wall_s}s · ${mm.rows_per_s ?? "–"} rows/s · busy ${mm.busy_s}s` };
  });
  const outcomes = job.modules.map((n) => {
    const p = job.progress[n] ?? { done: 0, errors: 0 };
    return { key: n, label: info[n]?.title ?? n, ok: p.done - p.errors, failed: p.errors, pending: job.total - p.done };
  });
  const moduleRows = job.modules.map((n) => {
    const mm = m.modules[n];
    return { key: n, task: info[n]?.title ?? n, engine: mm?.engine ?? "local CPU", rows: mm?.rows ?? 0,
             rate: mm?.rows_per_s ?? "–", wall: mm?.wall_s ?? 0, busy: mm?.busy_s ?? 0, par: mm?.parallelism ?? "–",
             p50: mm?.batch_ms.p50 ?? "–", p95: mm?.batch_ms.p95 ?? "–", errors: mm?.errors ?? 0 };
  });
  const engineRows = Object.entries(m.engines).map(([name, e]) => ({
    key: name, engine: name, kind: e.kind, requests: e.requests, items: e.items, inflight: e.inflight,
    p50: e.latency_ms.p50 ?? "–", p95: e.latency_ms.p95 ?? "–", errors: e.errors, retries: e.retries,
  }));
  const live = !isTerminal(job);

  return (
    <div className="perf">
      <div className="stat-row">
        <Tile label="Records processed" value={`${num(job.done)} / ${num(job.total)}`}
              hint={live ? `${job.percent.toFixed(0)}% of all task work` : job.status} />
        <Tile label="Elapsed" value={duration(m.wall_s)} hint={live && job.eta_s != null ? `≈ ${duration(job.eta_s)} left` : undefined} />
        <Tile label="Average" value={`${m.rows_per_s ?? "–"} records/s`} hint="every task, end to end" />
        <Tile label="Peak" value={`${m.peak_rows_per_s} records/s`} hint="best second" />
        <Tile label="Failed rows" value={num(job.failed_rows)} hint={job.failed_rows ? "see Rows → Errors" : "none"} />
      </div>

      <div className="card-grid card-grid-2">
        <ChartCard title="Records completed" chart={
          <LineChart points={done} ariaLabel="Records completed over time" xLabel="since start" />}
          rows={done.map((p) => ({ t: `${p.x}s`, records: p.y }))} rowKey="t"
          columns={[{ title: "Time", dataIndex: "t" }, { title: "Records done", dataIndex: "records", align: "right" }]} />
        <ChartCard title="Throughput (records/s, trailing average)" chart={
          <LineChart points={smooth} ariaLabel="Throughput over time" xLabel="since start" format={(v) => v.toFixed(v < 10 ? 1 : 0)} />}
          rows={smooth.map((p) => ({ t: `${p.x}s`, rate: p.y }))} rowKey="t"
          columns={[{ title: "Time", dataIndex: "t" }, { title: "Records/s", dataIndex: "rate", align: "right" }]} />
        <ChartCard title="When each task ran" extra={<span className="muted small">colour = engine</span>}
          chart={<Timeline spans={spans} total={m.wall_s} groups={engines.map((e) => ({ key: e, label: e, color: colorOf(e) }))} />}
          rows={moduleRows} rowKey="key"
          columns={[{ title: "Task", dataIndex: "task" }, { title: "Engine", dataIndex: "engine" },
                    { title: "Wall s", dataIndex: "wall", align: "right" }, { title: "Rows/s", dataIndex: "rate", align: "right" }]} />
        <ChartCard title="Outcome per task" chart={<OutcomeBars rows={outcomes} />} rows={outcomes} rowKey="key"
          columns={[{ title: "Task", dataIndex: "label" }, { title: "Processed", dataIndex: "ok", align: "right" },
                    { title: "Failed", dataIndex: "failed", align: "right" }, { title: "Pending", dataIndex: "pending", align: "right" }]} />
      </div>

      <Card size="small" className="module-card" title="Tasks" style={{ marginTop: 16 }}>
        <Table size="small" rowKey="key" dataSource={moduleRows} pagination={false} scroll={{ x: "max-content" }}
          columns={[
            { title: "Task", dataIndex: "task" }, { title: "Engine", dataIndex: "engine" },
            { title: "Rows", dataIndex: "rows", align: "right" }, { title: "Rows/s", dataIndex: "rate", align: "right" },
            { title: "Wall s", dataIndex: "wall", align: "right" }, { title: "Busy s", dataIndex: "busy", align: "right" },
            { title: "Parallelism", dataIndex: "par", align: "right" },
            { title: "Batch p50 ms", dataIndex: "p50", align: "right" }, { title: "Batch p95 ms", dataIndex: "p95", align: "right" },
            { title: "Errors", dataIndex: "errors", align: "right" },
          ]} />
      </Card>
      <Card size="small" className="module-card" title="Engines (since the backend started)" style={{ marginTop: 16 }}>
        <Table size="small" rowKey="key" dataSource={engineRows} pagination={false} scroll={{ x: "max-content" }}
          columns={[
            { title: "Engine", dataIndex: "engine" }, { title: "Kind", dataIndex: "kind" },
            { title: "Requests", dataIndex: "requests", align: "right" }, { title: "Items", dataIndex: "items", align: "right" },
            { title: "In flight", dataIndex: "inflight", align: "right" },
            { title: "Latency p50 ms", dataIndex: "p50", align: "right" }, { title: "p95 ms", dataIndex: "p95", align: "right" },
            { title: "Errors", dataIndex: "errors", align: "right" }, { title: "Retries", dataIndex: "retries", align: "right" },
          ]} />
      </Card>
    </div>
  );
}
