import { DeleteOutlined } from "@ant-design/icons";
import { App, Button, Progress, Tooltip } from "antd";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/endpoints";
import { keys, useJobs } from "../../hooks/queries";
import { ago, plural } from "../../lib/format";
import { StatusTag } from "../common/StatusTag";

/** Runs kept in the server's memory (until restart or expiry): reopen or forget them. */
export function RecentRuns({ onOpen }: { onOpen: (id: string) => void }) {
  const { data } = useJobs();
  const qc = useQueryClient();
  const { message } = App.useApp();
  if (!data?.length) return null;

  const remove = async (id: string) => {
    try {
      await api.remove(id);
      await qc.invalidateQueries({ queryKey: keys.jobs });
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  return (
    <section className="panel" aria-labelledby="recent-title">
      <div className="section-title" id="recent-title">Recent runs</div>
      <ul className="run-list">
        {data.map((j) => (
          <li key={j.id} className="run-item">
            <button type="button" className="run-open" onClick={() => onOpen(j.id)}>
              <span className="run-name">{j.filename}</span>
              <span className="run-meta">{plural(j.total, "row")} · {plural(j.modules.length, "analysis", "analyses")} · {ago(j.created_at)}</span>
            </button>
            {j.status === "running"
              ? <Progress percent={Math.round(j.percent)} size="small" style={{ width: 120, margin: 0 }} />
              : <StatusTag status={j.status} />}
            <Tooltip title="Forget this run">
              <Button type="text" size="small" icon={<DeleteOutlined />} aria-label={`Delete ${j.filename}`}
                      onClick={() => remove(j.id)} />
            </Tooltip>
          </li>
        ))}
      </ul>
    </section>
  );
}
