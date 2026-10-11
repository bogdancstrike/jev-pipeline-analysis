import { ArrowLeftOutlined, DownloadOutlined, StopOutlined } from "@ant-design/icons";
import { Alert, App, Button, Popover, Progress, Space, Tooltip } from "antd";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/endpoints";
import type { JobSnapshot, ModuleInfo } from "../../api/types";
import { isTerminal, keys } from "../../hooks/queries";
import { duration, num, plural } from "../../lib/format";
import { StatusTag } from "../common/StatusTag";

function ModuleProgress({ job, modules }: { job: JobSnapshot; modules: ModuleInfo[] }) {
  const title = (n: string) => modules.find((m) => m.name === n)?.title ?? n;
  return (
    <div className="module-progress">
      {job.modules.map((n) => {
        const p = job.progress[n];
        return (
          <div key={n} className="module-progress-row">
            <span>{title(n)}</span>
            <Progress percent={Math.floor((p.done / Math.max(1, job.total)) * 100)} size="small"
                      status={p.errors ? "exception" : p.done >= job.total ? "success" : "active"} />
            <span className="muted small">{num(p.done)}/{num(job.total)}{p.errors ? ` · ${p.errors} err` : ""}</span>
          </div>
        );
      })}
    </div>
  );
}

export function JobHeader({ job, modules, onBack }: { job: JobSnapshot; modules: ModuleInfo[]; onBack: () => void }) {
  const qc = useQueryClient();
  const { message } = App.useApp();
  const terminal = isTerminal(job);

  const cancel = async () => {
    try {
      qc.setQueryData(keys.job(job.id), await api.cancel(job.id));
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  return (
    <div className="job-header">
      <div className="job-header-top">
        <div className="job-title-block">
          <Button type="text" size="small" icon={<ArrowLeftOutlined />} onClick={onBack} className="back-btn">
            New run
          </Button>
          <div className="job-title-row">
            <h1 className="page-title" title={job.filename}>{job.filename}</h1>
            <StatusTag status={job.status} />
          </div>
          <div className="muted">
            {plural(job.total, "row")} · {plural(job.modules.length, "analysis", "analyses")}
            {job.status === "running" && <> · {job.rows_per_s} rows/s · {job.eta_s != null ? `about ${duration(job.eta_s)} left` : "estimating…"}</>}
            {terminal && <> · took {duration(job.elapsed_s)}</>}
            {job.failed_rows > 0 && <> · <span className="text-danger">{job.failed_rows} rows with errors</span></>}
          </div>
        </div>
        <Space wrap>
          {!terminal && <Button icon={<StopOutlined />} onClick={cancel}>Cancel</Button>}
          <Tooltip title={terminal ? undefined : "Available when the run stops"}>
            <Button type="primary" icon={<DownloadOutlined />} disabled={!terminal}
                    href={terminal ? api.resultUrl(job.id) : undefined}>
              {job.status === "done" || !terminal ? "Download CSV" : "Download partial CSV"}
            </Button>
          </Tooltip>
        </Space>
      </div>
      {!terminal && (
        <Popover content={<ModuleProgress job={job} modules={modules} />} placement="bottomLeft" title="Per analysis">
          <div className="overall-progress" tabIndex={0} aria-label="Progress details">
            <Progress percent={Math.floor(job.percent)} status="active" />
          </div>
        </Popover>
      )}
      {job.status === "failed" && <Alert type="error" showIcon title="The run stopped" description={job.error} />}
    </div>
  );
}
