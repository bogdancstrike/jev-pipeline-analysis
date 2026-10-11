import { DeleteOutlined } from "@ant-design/icons";
import { App, Button, Progress, Table, Tooltip } from "antd";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "../api/endpoints";
import type { JobSnapshot, RunRecord } from "../api/types";
import { EmptyState } from "../components/common/EmptyState";
import { StatusTag } from "../components/common/StatusTag";
import { keys, useJobs, useRuns } from "../hooks/queries";
import { ago, duration, num, plural } from "../lib/format";

interface Row {
  id: string; filename: string; status: JobSnapshot["status"]; total: number; modules: number;
  created_at: number; wall_s: number | null; rate: number | null; failed: number; live: boolean; percent: number;
}

/** Every run: live ones from the server's memory, finished ones also from the database. */
export function RunsPage({ onOpen }: { onOpen: (id: string) => void }) {
  const jobs = useJobs();
  const runs = useRuns();
  const qc = useQueryClient();
  const { message } = App.useApp();

  const live = new Map((jobs.data ?? []).map((j) => [j.id, j]));
  const rows: Row[] = (jobs.data ?? []).map((j) => ({
    id: j.id, filename: j.filename, status: j.status, total: j.total, modules: j.modules.length, created_at: j.created_at,
    wall_s: j.elapsed_s, rate: j.rows_per_s, failed: j.failed_rows, live: true, percent: j.percent,
  }));
  for (const r of (runs.data ?? []) as RunRecord[]) {
    if (live.has(r.id)) continue;
    rows.push({ id: r.id, filename: r.filename, status: r.status, total: r.total, modules: r.modules.length,
                created_at: r.created_at, wall_s: r.wall_s, rate: r.rows_per_s, failed: r.metrics.failed_rows ?? 0,
                live: false, percent: 100 });
  }
  rows.sort((a, b) => b.created_at - a.created_at);

  const remove = async (id: string) => {
    try {
      await api.remove(id);
      await qc.invalidateQueries({ queryKey: keys.jobs });
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  if (!rows.length && !jobs.isLoading) {
    return <div className="panel"><EmptyState title="No runs yet" hint="Start one from New analysis." /></div>;
  }
  return (
    <div className="panel panel-flush">
      <Table<Row> rowKey="id" dataSource={rows} loading={jobs.isLoading} size="middle" scroll={{ x: "max-content" }}
        pagination={{ pageSize: 25, hideOnSinglePage: true }}
        onRow={(r) => ({ onClick: () => r.live && onOpen(r.id), className: r.live ? "row-click" : undefined })}
        columns={[
          { title: "Run", dataIndex: "filename", render: (f: string, r) => (
              <div><div className="run-name">{f}</div><div className="run-meta">{ago(r.created_at)}{!r.live && " · history only"}</div></div>) },
          { title: "Status", dataIndex: "status", render: (s: Row["status"], r) => s === "running"
              ? <Progress percent={Math.floor(r.percent)} size="small" style={{ width: 140 }} /> : <StatusTag status={s} /> },
          { title: "Records", dataIndex: "total", align: "right", render: (n: number) => num(n) },
          { title: "Analyses", dataIndex: "modules", align: "right", render: (n: number) => plural(n, "task") },
          { title: "Took", dataIndex: "wall_s", align: "right", render: (s: number | null) => duration(s) },
          { title: "Records/s", dataIndex: "rate", align: "right", render: (v: number | null) => v ?? "–" },
          { title: "Failed rows", dataIndex: "failed", align: "right", render: (n: number) => n ? <span className="text-danger">{num(n)}</span> : "0" },
          { title: "", key: "x", width: 48, render: (_: unknown, r) => r.live && (
              <Tooltip title="Forget this run (keeps its history)">
                <Button type="text" size="small" icon={<DeleteOutlined />} aria-label={`Delete ${r.filename}`}
                        onClick={(e) => { e.stopPropagation(); void remove(r.id); }} />
              </Tooltip>) },
        ]} />
    </div>
  );
}
