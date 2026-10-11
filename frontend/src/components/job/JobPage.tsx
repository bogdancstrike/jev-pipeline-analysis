import { Badge, Button, Result, Skeleton, Tabs } from "antd";
import { useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import type { AppConfig } from "../../api/types";
import { useLiveJob, useRows, useSummary } from "../../hooks/queries";
import { useDebounced } from "../../hooks/useDebounced";
import { useStoredState } from "../../hooks/useUrlState";
import { ErrorAlert } from "../common/ErrorAlert";
import { RowDrawer } from "../rows/RowDrawer";
import { defaultColumns, RowsView, type RowMode } from "../rows/RowsView";
import { JobHeader } from "./JobHeader";
import { Overview, type Filter } from "./Overview";
import { PerformanceTab } from "./PerformanceTab";

const PAGE_SIZE = 25;

export function JobPage({ jobId, config, onBack }: { jobId: string; config: AppConfig; onBack: () => void }) {
  const jobQ = useLiveJob(jobId);
  const job = jobQ.data;
  const summaryQ = useSummary(job);

  const [tab, setTab] = useState<"overview" | "rows" | "performance">("overview");
  const [filters, setFilters] = useState<Filter[]>([]);
  const [mode, setMode] = useState<RowMode>("all");
  const [search, setSearch] = useState("");
  const [pageNo, setPageNo] = useState(1);
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const [storedColumns, setColumns] = useStoredState<string[] | null>("triage.columns", null);
  const q = useDebounced(search, 300);

  // A different job, or different filters: back to page 1.
  useEffect(() => { setPageNo(1); }, [jobId, filters, mode, q]);
  useEffect(() => { setFilters([]); setMode("all"); setSearch(""); setOpenIdx(null); setTab("overview"); }, [jobId]);

  const rowsQ = useRows(job, { offset: (pageNo - 1) * PAGE_SIZE, limit: PAGE_SIZE, filters,
                               review: mode === "review", errors: mode === "errors", q });

  if (jobQ.error) {
    const gone = jobQ.error instanceof ApiError && jobQ.error.status === 404;
    return gone
      ? <Result status="404" title="This run is gone" subTitle="Runs live in the server's memory: it was deleted, expired or the server restarted."
                extra={<Button type="primary" onClick={onBack}>Start a new run</Button>} />
      : <ErrorAlert error={jobQ.error} onRetry={() => jobQ.refetch()} />;
  }
  if (!job) return <Skeleton active />;

  const modules = config.modules;
  const columns = (storedColumns ?? defaultColumns(job)).filter((c) => job.modules.includes(c));

  const addFilter = (f: Filter) => {
    setFilters((cur) => [...cur.filter(([m]) => m !== f[0]), f]); // one value per module
    setTab("rows");
  };

  return (
    <div className="job-page">
      <JobHeader job={job} modules={modules} onBack={onBack} />
      <Tabs
        activeKey={tab}
        onChange={(k) => setTab(k as "overview" | "rows" | "performance")}
        items={[
          {
            key: "overview", label: "Overview",
            children: <Overview job={job} summary={summaryQ.data} error={summaryQ.error} modules={modules}
                                onFilter={addFilter} onReview={() => { setMode("review"); setTab("rows"); }}
                                onErrors={() => { setMode("errors"); setTab("rows"); }} onOpenRow={setOpenIdx} />,
          },
          {
            key: "performance", label: "Performance",
            children: tab === "performance" ? <PerformanceTab job={job} modules={modules} /> : null,
          },
          {
            key: "rows",
            label: <span>Rows <Badge count={rowsQ.data?.total ?? job.total} overflowCount={999999} color="var(--surface-2)"
                                       style={{ color: "var(--text-2)", boxShadow: "none" }} showZero /></span>,
            children: (
              <RowsView job={job} modules={modules} page={rowsQ.data} loading={rowsQ.isFetching} error={rowsQ.error}
                        onRetry={() => rowsQ.refetch()} pageNo={pageNo} pageSize={PAGE_SIZE} onPage={setPageNo}
                        search={search} onSearch={setSearch} mode={mode} onMode={setMode}
                        filters={filters} onRemoveFilter={(f) => setFilters((cur) => cur.filter((x) => x !== f))}
                        onClearAll={() => { setFilters([]); setMode("all"); setSearch(""); }}
                        columns={columns} onColumns={setColumns} onOpen={setOpenIdx} />
            ),
          },
        ]}
      />
      <RowDrawer job={job} modules={modules} idx={openIdx} onClose={() => setOpenIdx(null)} onOpen={setOpenIdx}
                 onFilter={(m, v) => { setOpenIdx(null); addFilter([m, v]); }} />
    </div>
  );
}
