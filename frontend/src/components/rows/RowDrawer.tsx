import { LeftOutlined, RightOutlined } from "@ant-design/icons";
import { Alert, Button, Drawer, Skeleton, Space, Tooltip } from "antd";

import type { EntitiesResult, JobSnapshot, ModuleInfo, ResolvedResult } from "../../api/types";
import { isTerminal, useRow } from "../../hooks/queries";
import { ErrorAlert } from "../common/ErrorAlert";
import { rendererFor } from "../results/registry";
import { HighlightedText } from "./HighlightedText";

interface Props {
  job: JobSnapshot;
  modules: ModuleInfo[];
  idx: number | null;
  onClose: () => void;
  onOpen: (idx: number) => void;
  onFilter: (module: string, value: string) => void;
}

/** One row in full: the text with entities marked, then every analysis, labels first. */
export function RowDrawer({ job, modules, idx, onClose, onOpen, onFilter }: Props) {
  const row = useRow(job.id, idx, !isTerminal(job));
  const r = row.data;
  const inJob = modules.filter((m) => job.modules.includes(m.name));
  const labels = inJob.filter((m) => m.kind === "label");
  const structured = inJob.filter((m) => m.kind !== "label" && m.kind !== "entities");
  const ner = r?.results["ner"] as EntitiesResult | null | undefined;
  const er = r?.results["entity_resolution"] as ResolvedResult | null | undefined;
  const title = (n: string) => modules.find((m) => m.name === n)?.title ?? n;

  const nav = idx !== null && (
    <Space size={4}>
      <Tooltip title="Previous row"><Button size="small" icon={<LeftOutlined />} disabled={idx <= 0}
               onClick={() => onOpen(idx - 1)} aria-label="Previous row" /></Tooltip>
      <Tooltip title="Next row"><Button size="small" icon={<RightOutlined />} disabled={idx >= job.total - 1}
               onClick={() => onOpen(idx + 1)} aria-label="Next row" /></Tooltip>
    </Space>
  );

  return (
    <Drawer open={idx !== null} onClose={onClose} size={820} destroyOnHidden
            title={r ? `Row ${r.id}` : "Row"} extra={nav}>
      {row.error ? <ErrorAlert error={row.error} onRetry={() => row.refetch()} /> : !r ? <Skeleton active /> : (
        <div className="drawer-body">
          {r.review.length > 0 && (
            <Alert type="warning" showIcon title={`Worth a human look: ${r.review.map(title).join(", ")} answered with low confidence.`} />
          )}
          {Object.entries(r.errors).map(([m, msg]) => (
            <Alert key={m} type="error" showIcon title={`${title(m)} failed`} description={msg} />
          ))}

          <section>
            <HighlightedText text={r.text} spans={ner?.spans ?? []} resolved={er?.entities ?? []} modules={modules} />
          </section>

          {labels.length > 0 && (
            <section>
              <div className="section-title">Classification</div>
              <div className="label-grid">
                {labels.map((m) => (
                  <div key={m.name} className="label-card">
                    <div className="label-card-title">{m.title}</div>
                    {rendererFor(m.kind).detail(r.results[m.name], { module: m, modules })}
                  </div>
                ))}
              </div>
            </section>
          )}

          {inJob.some((m) => m.name === "ner") && !inJob.some((m) => m.name === "entity_resolution") && (
            <section>
              <div className="section-title">Entities</div>
              {rendererFor("entities").detail(r.results["ner"], { module: inJob.find((m) => m.name === "ner")!, modules })}
            </section>
          )}

          {structured.map((m) => (
            <section key={m.name}>
              <div className="section-title">{m.title}</div>
              {rendererFor(m.kind).detail(r.results[m.name], {
                module: m, modules,
                onFilter: (v) => onFilter(m.name, v),
                onOpenRow: onOpen,
              })}
            </section>
          ))}
        </div>
      )}
    </Drawer>
  );
}
