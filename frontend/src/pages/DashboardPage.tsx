import { ArrowRightOutlined, DashboardOutlined, FileDoneOutlined, HistoryOutlined, PlusOutlined, ClockCircleOutlined } from "@ant-design/icons";
import { Button, Empty, Progress, Skeleton, Table, Tag } from "antd";

import type { JobSnapshot, RunRecord } from "../api/types";
import { ChartCard } from "../components/charts/ChartCard";
import { LineChart, useStableMax } from "../components/charts/LineChart";
import { ErrorAlert } from "../components/common/ErrorAlert";
import { PageHeader } from "../components/ui/PageHeader";
import { StatRow, StatTile } from "../components/ui/StatTile";
import { useAppConfig, useEngineMetrics, useJobMetrics, useJobs, useRuns } from "../hooks/queries";
import { ago, duration, num, plural } from "../lib/format";

function RunBars({ runs, titleOf }: { runs: RunRecord[]; titleOf: (n: string) => string }) {
  const data = runs.slice(0, 15);
  const max = Math.max(1, ...data.map((r) => r.rows_per_s ?? 0));
  return <div className="dashboard-runbars">{data.map((r) => (
    <div key={r.id} className="dashboard-runbar">
      <div className="dashboard-runbar-heading">
        <div className="dashboard-runbar-name"><strong title={r.filename}>{r.filename}</strong><span>{num(r.total)} records · {ago(r.created_at)}</span></div>
        <strong className="dashboard-rate">{r.rows_per_s ?? "–"}<span> /s</span></strong>
      </div>
      <div className="dashboard-bar-track" aria-hidden><span style={{ width: `${((r.rows_per_s ?? 0) / max) * 100}%` }} /></div>
      <div className="dashboard-runbar-foot"><span title={r.modules.map(titleOf).join(", ")}>{r.modules.map(titleOf).join(" · ")}</span><span>{duration(r.wall_s)}</span></div>
    </div>
  ))}</div>;
}

function LiveJob({ job }: { job: JobSnapshot }) {
  const metrics = useJobMetrics(job);
  const config = useAppConfig();
  const xMax = useStableMax(job.elapsed_s + (job.eta_s ?? 0), 10);
  const rowScoped = job.modules.filter((n) => config.data?.modules.find((x) => x.name === n)?.scope !== "job");
  const points = (metrics.data?.timeline ?? []).map((p) => ({ x: p.t, y: rowScoped.length ? Math.min(...rowScoped.map((n) => p.done[n] ?? 0)) : job.done }));
  return <div className="dashboard-live-detail">
    <div>
      <div className="section-title">In progress</div>
      <a className="dashboard-live-name" href={`/runs?job=${encodeURIComponent(job.id)}`}>{job.filename}<ArrowRightOutlined /></a>
      <Progress percent={Math.floor(job.percent)} size="small" status="active" />
      <div className="dashboard-live-metrics">
        <div><strong>{num(job.done)} <span>/ {num(job.total)}</span></strong><span>records processed</span></div>
        <div><strong>{job.rows_per_s}/s</strong><span>{job.eta_s != null ? `≈ ${duration(job.eta_s)} remaining` : "calculating time remaining"}</span></div>
        <div><strong>{duration(job.elapsed_s)}</strong><span>elapsed</span></div>
      </div>
    </div>
    <div>{metrics.error ? <ErrorAlert error={metrics.error} onRetry={() => metrics.refetch()} /> : <LineChart points={points} height={150} ariaLabel="Records completed over time" xLabel="since start" yMax={job.total} xMax={xMax} />}</div>
  </div>;
}

export function DashboardPage() {
  const runs = useRuns();
  const jobs = useJobs();
  const engines = useEngineMetrics();
  const config = useAppConfig();
  const done = (runs.data ?? []).filter((r) => r.status === "done");
  const active = (jobs.data ?? []).filter((j) => j.status === "running");
  const queued = (jobs.data ?? []).filter((j) => j.status === "queued");
  const title = (n: string) => config.data?.modules.find((m) => m.name === n)?.title ?? n;
  const totalRecords = done.reduce((sum, r) => sum + r.total, 0);
  const totalTime = done.reduce((sum, r) => sum + (r.wall_s ?? 0), 0);
  const engineRows = Object.entries(engines.data ?? {});
  const ready = engineRows.filter(([, e]) => e.ready).length;
  const perTask = new Map<string, number[]>();
  for (const run of done) for (const [name, metric] of Object.entries(run.metrics.modules ?? {})) {
    if (metric.rows_per_s != null) perTask.set(name, [...(perTask.get(name) ?? []), metric.rows_per_s]);
  }
  const taskRows = [...perTask.entries()].map(([name, rates]) => ({
    key: name, task: title(name), runs: rates.length,
    mean: Math.round(rates.reduce((a, b) => a + b, 0) / rates.length * 10) / 10, best: Math.max(...rates),
  })).sort((a, b) => b.mean - a.mean);
  const hasRuns = runs.data !== undefined;
  const stat = (value: string) => hasRuns ? value : "–";

  return <div className="dashboard">
    <PageHeader title="Dashboard" description="Your analysis activity, processing performance and model health."
      actions={<><Button href="/runs">View runs</Button><Button type="primary" icon={<PlusOutlined />} href="/">New analysis</Button></>} />
    {runs.error ? <ErrorAlert error={runs.error} onRetry={() => runs.refetch()} /> : null}
    {jobs.error ? <ErrorAlert error={jobs.error} onRetry={() => jobs.refetch()} /> : null}
    <StatRow>
      <StatTile icon={<HistoryOutlined />} label="Completed runs" value={stat(num(done.length))} hint="in saved history" />
      <StatTile icon={<FileDoneOutlined />} label="Records processed" value={stat(num(totalRecords))} hint="across completed runs" />
      <StatTile icon={<DashboardOutlined />} label="Average throughput" value={stat(totalTime ? `${(totalRecords / totalTime).toFixed(1)}/s` : "–")} hint="records per second" />
      <StatTile icon={<ClockCircleOutlined />} label="Processing time" value={stat(duration(totalTime))} hint="total completed run time" />
    </StatRow>
    <section className={`dashboard-activity${active.length ? " is-running" : ""}`} aria-label="Current activity">
      <div className="dashboard-activity-bar">
        <div><span className={`dot ${active.length ? "activity-active" : "activity-idle"}`} /><strong>{jobs.isLoading ? "Checking activity…" : jobs.error ? "Activity unavailable" : active.length ? `${plural(active.length, "analysis", "analyses")} running` : queued.length ? "Waiting to start" : "Ready for your next analysis"}</strong>
          {queued.length > 0 && <span className="meta-chip">{queued.length} queued</span>}</div>
        <span className="muted small">Activity refreshes every 5 seconds</span>
      </div>
      {active[0] && <LiveJob key={active[0].id} job={active[0]} />}
      {active.length > 1 && <div className="dashboard-other-jobs">{active.slice(1).map((job) => <a key={job.id} href={`/runs?job=${job.id}`}>{job.filename}<span>{job.percent.toFixed(0)}% <ArrowRightOutlined /></span></a>)}</div>}
    </section>
    <div className="dashboard-columns">
      <div className="dashboard-stack">
        <ChartCard title="Recent run performance" extra={<span className="muted small">Latest 15 · records/s</span>}
          chart={runs.isLoading ? <Skeleton active paragraph={{ rows: 4 }} /> : done.length ? <RunBars runs={done} titleOf={title} /> : <div className="dashboard-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Complete an analysis to see run performance." /><Button type="primary" href="/">Start an analysis</Button></div>}
          rows={done.slice(0, 15).map((r) => ({ id: r.id, run: r.filename, records: r.total, tasks: r.modules.length, took: duration(r.wall_s), rate: r.rows_per_s ?? 0 }))}
          rowKey="id" columns={[{ title: "Run", dataIndex: "run" }, { title: "Records", dataIndex: "records", align: "right" },
            { title: "Tasks", dataIndex: "tasks", align: "right" }, { title: "Time", dataIndex: "took", align: "right" }, { title: "Records/s", dataIndex: "rate", align: "right" }]} />
        <section className="dashboard-panel">
          <div className="dashboard-panel-head"><div><h3>Task throughput</h3><p>Average and best speed across completed runs, while sharing model resources.</p></div><span className="meta-chip">{plural(taskRows.length, "task")}</span></div>
          <Table size="small" rowKey="key" dataSource={taskRows} loading={runs.isLoading} pagination={false} scroll={{ x: "max-content" }}
            locale={{ emptyText: "Task timings appear after a run completes." }} columns={[
              { title: "Task", dataIndex: "task" }, { title: "Runs", dataIndex: "runs", align: "right" },
              { title: "Average /s", dataIndex: "mean", align: "right", render: (v: number) => <strong>{v}</strong> },
              { title: "Best /s", dataIndex: "best", align: "right" },
            ]} />
        </section>
        <p className="dashboard-scope">Run statistics use the latest 200 saved runs. Deleted runs are excluded.</p>
      </div>
      <section className="dashboard-panel dashboard-engine-panel">
        <div className="dashboard-panel-head"><div><h3>Model engines</h3><p>Live health and request performance</p></div><Tag color={ready === engineRows.length && ready > 0 ? "success" : "default"}>{ready}/{engineRows.length} ready</Tag></div>
        {engines.error ? <ErrorAlert error={engines.error} onRetry={() => engines.refetch()} /> : null}
        {engines.isLoading ? <Skeleton active /> : engineRows.length ? engineRows.map(([name, engine]) => <article key={name} className="dashboard-engine">
          <div className="dashboard-engine-heading"><div><strong>{name}</strong><span className="muted small">{engine.kind}</span></div><Tag color={engine.ready ? "success" : "processing"}>{engine.ready ? "Ready" : "Loading"}</Tag></div>
          <dl className="dashboard-engine-metrics">
            <div><dt>Requests</dt><dd>{num(engine.requests)}</dd></div><div><dt>Items</dt><dd>{num(engine.items)}</dd></div><div><dt>In flight</dt><dd>{num(engine.inflight)}</dd></div>
            <div><dt>Median latency</dt><dd>{engine.latency_ms.p50 != null ? `${num(engine.latency_ms.p50)} ms` : "–"}</dd></div>
            <div><dt>p95 latency</dt><dd>{engine.latency_ms.p95 != null ? `${num(engine.latency_ms.p95)} ms` : "–"}</dd></div>
            <div><dt>Errors / retries</dt><dd className={engine.errors ? "text-danger" : undefined}>{num(engine.errors)} / {num(engine.retries)}</dd></div>
          </dl>
        </article>) : <p className="muted">No engines reporting yet.</p>}
        <div className="dashboard-engine-foot">Engine counters cover the current backend session.<br />Refreshes every 5 seconds.</div>
      </section>
    </div>
  </div>;
}
