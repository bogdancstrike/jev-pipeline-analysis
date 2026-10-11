import { DeleteOutlined } from "@ant-design/icons";
import { App, Button, Progress, Table } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/endpoints";
import type { JobSnapshot, RunRecord } from "../api/types";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorAlert } from "../components/common/ErrorAlert";
import { StatusTag } from "../components/common/StatusTag";
import { PageHeader } from "../components/ui/PageHeader";
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
  const { message, modal } = App.useApp();
  const [selected, setSelected] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);

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

  const selectedIds = selected.filter((id) => rows.some((r) => r.id === id));
  const remove = async (ids: string[]) => {
    setDeleting(true);
    try {
      await api.deleteRuns(ids);
      const removed = new Set(ids);
      // Update both caches immediately; refetching also reconciles work from other tabs.
      await Promise.all([qc.cancelQueries({ queryKey: keys.jobs }), qc.cancelQueries({ queryKey: keys.runs })]);
      qc.setQueryData<JobSnapshot[]>(keys.jobs, (old) => old?.filter((r) => !removed.has(r.id)));
      qc.setQueryData<RunRecord[]>(keys.runs, (old) => old?.filter((r) => !removed.has(r.id)));
      ids.forEach((id) => qc.removeQueries({ queryKey: keys.job(id) }));
      setSelected((old) => old.filter((id) => !removed.has(id)));
      message.success(`${plural(ids.length, "run")} deleted. Dashboard statistics updated.`);
      await Promise.all([qc.invalidateQueries({ queryKey: keys.jobs }), qc.invalidateQueries({ queryKey: keys.runs })]);
    } catch (e) {
      message.error((e as Error).message);
      throw e;
    } finally {
      setDeleting(false);
    }
  };
  const confirmDelete = () => {
    const ids = [...selectedIds];
    const active = rows.filter((r) => ids.includes(r.id) && (r.status === "running" || r.status === "queued")).length;
    modal.confirm({
      title: `Delete ${plural(ids.length, "run")}?`,
      content: `Their results and saved history will be permanently removed and excluded from dashboard statistics.${active ? ` ${plural(active, "active run")} will be stopped.` : ""}`,
      okText: "Delete runs", okButtonProps: { danger: true }, cancelText: "Keep runs",
      onOk: () => remove(ids),
    });
  };
  const running = rows.filter((r) => r.status === "running" || r.status === "queued").length;
  return (
    <>
    <PageHeader title="Runs" description="Open an analysis to explore its results. Select runs to remove their results, history and dashboard statistics."
                meta={<><span className="meta-chip">{rows.length} runs</span>{running > 0 && <span className="meta-chip">{running} running</span>}</>} />
    {jobs.error ? <ErrorAlert error={jobs.error} onRetry={() => jobs.refetch()} /> : null}
    {runs.error ? <ErrorAlert error={runs.error} onRetry={() => runs.refetch()} /> : null}
    <div className="panel panel-flush">
      <Table<Row> rowKey="id" dataSource={rows} loading={jobs.isLoading || runs.isLoading} size="middle" scroll={{ x: "max-content" }}
        title={() => <div className="runs-table-toolbar">
          <div><strong>{selectedIds.length ? `${selectedIds.length} selected` : "Run history"}</strong>
            <span className="muted small">{selectedIds.length ? "Selection is kept across pages" : "Select runs using the checkboxes"}</span></div>
          <div className="admin-actions">
            {selectedIds.length > 0 && <Button type="text" disabled={deleting} onClick={() => setSelected([])}>Clear selection</Button>}
            <Button danger icon={<DeleteOutlined />} disabled={!selectedIds.length} loading={deleting} onClick={confirmDelete}>
              Delete selected{selectedIds.length > 0 ? ` (${selectedIds.length})` : ""}
            </Button>
          </div>
        </div>}
        rowSelection={{
          selectedRowKeys: selectedIds, preserveSelectedRowKeys: true,
          onChange: (ids) => setSelected(ids.map(String)),
          getCheckboxProps: (r) => ({ disabled: deleting, "aria-label": `Select ${r.filename}` }),
          getTitleCheckboxProps: () => ({ disabled: deleting, "aria-label": "Select all runs on this page" }),
          onCell: () => ({ onClick: (e) => e.stopPropagation() }),
        }}
        locale={{ emptyText: <EmptyState title="No runs yet" hint="Start one from New analysis." /> }}
        pagination={{ pageSize: 25, hideOnSinglePage: true }}
        onRow={(r) => ({ onClick: () => r.live && onOpen(r.id), className: r.live ? "row-click" : undefined })}
        columns={[
          { title: "Run", dataIndex: "filename", render: (f: string, r) => (
              <div><div className="run-name">{r.live ? <button type="button" className="link-btn" onClick={(e) => { e.stopPropagation(); onOpen(r.id); }}>{f}</button> : f}</div><div className="run-meta">{ago(r.created_at)}{!r.live && " · history only"}</div></div>) },
          { title: "Status", dataIndex: "status", render: (s: Row["status"], r) => s === "running"
              ? <Progress percent={Math.floor(r.percent)} size="small" style={{ width: 140 }} /> : <StatusTag status={s} /> },
          { title: "Records", dataIndex: "total", align: "right", render: (n: number) => num(n) },
          { title: "Analyses", dataIndex: "modules", align: "right", render: (n: number) => plural(n, "task") },
          { title: "Took", dataIndex: "wall_s", align: "right", render: (s: number | null) => duration(s) },
          { title: "Records/s", dataIndex: "rate", align: "right", render: (v: number | null) => v ?? "–" },
          { title: "Failed rows", dataIndex: "failed", align: "right", render: (n: number) => n ? <span className="text-danger">{num(n)}</span> : "0" },
        ]} />
    </div>
    </>
  );
}
