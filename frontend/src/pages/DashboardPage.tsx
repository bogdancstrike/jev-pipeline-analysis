import { Card, Empty, Table } from "antd";

import type { RunRecord } from "../api/types";
import { ChartCard } from "../components/charts/ChartCard";
import { LineChart } from "../components/charts/LineChart";
import { useAppConfig, useEngineMetrics, useJobMetrics, useJobs, useRuns } from "../hooks/queries";
import { duration, num } from "../lib/format";

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return <div className="stat-tile"><span className="stat-label">{label}</span><span className="stat-value">{value}</span>{hint && <span className="stat-hint">{hint}</span>}</div>;
}

/** One labelled horizontal bar per run, newest first, value at the tip (no rank colouring). */
function RunBars({ runs, titleOf }: { runs: RunRecord[]; titleOf: (n: string) => string }) {
  const data = runs.slice(0, 15);
  const max = Math.max(1, ...data.map((r) => r.rows_per_s ?? 0));
  return (
    <div className="runbars">
      {data.map((r) => {
        const tasks = r.modules.length > 3 ? `${r.modules.length} tasks` : r.modules.map(titleOf).join(", ");
        return (
          <div key={r.id} className="runbar-row" title={`${r.filename} · ${r.total} records · ${r.rows_per_s ?? 0} records/s`}>
            <span className="runbar-label"><b>{r.filename}</b> <span className="muted">· {tasks}</span></span>
            <span className="runbar-track"><span className="runbar-fill" style={{ width: `${((r.rows_per_s ?? 0) / max) * 100}%` }} /></span>
            <span className="runbar-value">{r.rows_per_s ?? 0}/s</span>
          </div>
        );
      })}
    </div>
  );
}

function LiveJob() {
  const jobs = useJobs();
  const job = (jobs.data ?? []).find((j) => j.status === "running");
  const m = useJobMetrics(job);
  const config = useAppConfig();
  if (!job) return <Card size="small" className="module-card" title="Running now"><Empty description="Nothing running" image={Empty.PRESENTED_IMAGE_SIMPLE} /></Card>;
  const rowScoped = job.modules.filter((n) => config.data?.modules.find((x) => x.name === n)?.scope !== "job");
  const pts = (m.data?.timeline ?? []).map((p) => ({ x: p.t, y: Math.min(...rowScoped.map((n) => p.done[n] ?? 0)) }));
  return (
    <Card size="small" className="module-card" title={`Running now · ${job.filename}`}>
      <div className="stat-row">
        <Tile label="Records processed" value={`${num(job.done)} / ${num(job.total)}`} hint={`${job.percent.toFixed(0)}% of task work`} />
        <Tile label="Speed" value={`${job.rows_per_s} records/s`} hint={job.eta_s != null ? `≈ ${duration(job.eta_s)} left` : undefined} />
        <Tile label="Elapsed" value={duration(job.elapsed_s)} />
      </div>
      <LineChart points={pts} ariaLabel="Records completed over time" xLabel="since start" />
    </Card>
  );
}

/** The system at a glance: what runs now, how the engines behave, how past runs performed. */
export function DashboardPage() {
  const runs = useRuns();
  const engines = useEngineMetrics();
  const config = useAppConfig();
  const done = (runs.data ?? []).filter((r) => r.status === "done");
  const title = (n: string) => config.data?.modules.find((m) => m.name === n)?.title ?? n;
  const totalRecords = done.reduce((a, r) => a + r.total, 0);
  const totalTime = done.reduce((a, r) => a + (r.wall_s ?? 0), 0);

  // Per-task throughput across finished runs (mean of each run's rows/s for that task).
  const perTask = new Map<string, number[]>();
  for (const r of done) for (const [n, mm] of Object.entries(r.metrics.modules ?? {})) {
    if (mm.rows_per_s) perTask.set(n, [...(perTask.get(n) ?? []), mm.rows_per_s]);
  }
  const taskRows = [...perTask.entries()].map(([n, v]) => ({
    key: n, task: title(n), runs: v.length, mean: Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 10) / 10,
    best: Math.max(...v),
  })).sort((a, b) => b.mean - a.mean);
  const engineRows = Object.entries(engines.data ?? {}).map(([name, e]) => ({
    key: name, engine: name, kind: e.kind, ready: e.ready ? "ready" : "loading", requests: e.requests, items: e.items,
    inflight: e.inflight, p50: e.latency_ms.p50 ?? "–", p95: e.latency_ms.p95 ?? "–", errors: e.errors, retries: e.retries,
  }));

  return (
    <div className="dashboard">
      <div className="stat-row">
        <Tile label="Finished runs" value={num(done.length)} />
        <Tile label="Records processed" value={num(totalRecords)} />
        <Tile label="Average speed" value={totalTime ? `${(totalRecords / totalTime).toFixed(1)} records/s` : "–"} hint="all finished runs" />
        <Tile label="Engine requests" value={num(engineRows.reduce((a, e) => a + e.requests, 0))} hint="since the backend started" />
      </div>
      <div className="card-grid card-grid-2">
        <LiveJob />
        <ChartCard title="Records/s per run (latest 15)" chart={done.length ? <RunBars runs={done} titleOf={title} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          rows={done.map((r) => ({ id: r.id, run: r.filename, records: r.total, tasks: r.modules.length, took: duration(r.wall_s), rate: r.rows_per_s ?? 0 }))}
          rowKey="id" columns={[{ title: "Run", dataIndex: "run" }, { title: "Records", dataIndex: "records", align: "right" },
                                { title: "Tasks", dataIndex: "tasks", align: "right" }, { title: "Took", dataIndex: "took", align: "right" },
                                { title: "Records/s", dataIndex: "rate", align: "right" }]} />
      </div>
      <div className="card-grid card-grid-2" style={{ marginTop: 16 }}>
        <Card size="small" className="module-card" title="Engines (live)">
          <Table size="small" rowKey="key" dataSource={engineRows} pagination={false} scroll={{ x: "max-content" }} columns={[
            { title: "Engine", dataIndex: "engine" }, { title: "State", dataIndex: "ready" },
            { title: "Requests", dataIndex: "requests", align: "right" }, { title: "Items", dataIndex: "items", align: "right" },
            { title: "In flight", dataIndex: "inflight", align: "right" },
            { title: "p50 ms", dataIndex: "p50", align: "right" }, { title: "p95 ms", dataIndex: "p95", align: "right" },
            { title: "Errors", dataIndex: "errors", align: "right" }, { title: "Retries", dataIndex: "retries", align: "right" },
          ]} />
        </Card>
        <Card size="small" className="module-card" title="Task throughput across runs (rows/s, while sharing the GPU)">
          <Table size="small" rowKey="key" dataSource={taskRows} pagination={false} scroll={{ x: "max-content" }} columns={[
            { title: "Task", dataIndex: "task" }, { title: "Runs", dataIndex: "runs", align: "right" },
            { title: "Mean rows/s", dataIndex: "mean", align: "right" }, { title: "Best", dataIndex: "best", align: "right" },
          ]} />
        </Card>
      </div>
    </div>
  );
}
