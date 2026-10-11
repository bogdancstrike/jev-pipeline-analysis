import { LeftOutlined, RightOutlined } from "@ant-design/icons";
import { Alert, Badge, Button, Drawer, Skeleton, Space, Tabs, Tooltip } from "antd";
import { useState, type ReactNode } from "react";

import type { EntitiesResult, JobSnapshot, LabelResult, ModuleInfo, RelationsResult, ResolvedResult } from "../../api/types";
import { isTerminal, useRow } from "../../hooks/queries";
import { ErrorAlert } from "../common/ErrorAlert";
import { LabelTag } from "../results/LabelView";
import { rendererFor } from "../results/registry";
import { TextLabels } from "./TextLabels";

interface Props {
  job: JobSnapshot;
  modules: ModuleInfo[];
  idx: number | null;
  onClose: () => void;
  onOpen: (idx: number) => void;
  onFilter: (module: string, value: string) => void;
}

const tabLabel = (text: string, count?: number) => (
  <span className="tab-label">{text}{count !== undefined && <Badge count={count} showZero size="small" color="var(--surface-2)" className="tab-badge" />}</span>
);

/** One row, organized: the text and its labels first; entities, relations, fields, event on their own tabs. */
export function RowDrawer({ job, modules, idx, onClose, onOpen, onFilter }: Props) {
  const row = useRow(job.id, idx, !isTerminal(job));
  const [tab, setTab] = useState("text");
  const r = row.data;
  const by = (n: string) => modules.find((m) => m.name === n);
  const inJob = modules.filter((m) => job.modules.includes(m.name));
  const labels = inJob.filter((m) => m.kind === "label");
  const ner = r?.results["ner"] as EntitiesResult | null | undefined;
  const er = r?.results["entity_resolution"] as ResolvedResult | null | undefined;
  const rels = r?.results["relations"] as RelationsResult | null | undefined;
  const title = (n: string) => by(n)?.title ?? n;
  const ctx = (name: string) => ({ module: by(name)!, modules, onFilter: (v: string) => onFilter(name, v), onOpenRow: onOpen });

  // Header chips: the three labels that say most about a row, when they ran.
  const chips = ["language", "category", "risk"].filter((n) => job.modules.includes(n) && r?.results[n]).map((n) => (
    <LabelTag key={n} module={by(n)!} label={(r!.results[n] as LabelResult).label} compact={n === "language"} />
  ));

  const tabs: { key: string; label: ReactNode; children: ReactNode }[] = [];
  if (r) {
    tabs.push({
      key: "text", label: tabLabel("Text & labels"),
      children: (
        <div className="drawer-body">
          {r.review.length > 0 && <Alert type="warning" showIcon title={`Worth a human look: ${r.review.map(title).join(", ")} answered with low confidence.`} />}
          {Object.entries(r.errors).map(([m, msg]) => <Alert key={m} type="error" showIcon title={`${title(m)} failed`} description={msg} />)}
          <TextLabels row={r} labels={labels} modules={modules} spans={ner?.spans ?? []} resolved={er?.entities ?? []} onFilter={onFilter} />
        </div>
      ),
    });
    if (job.modules.includes("ner")) {
      tabs.push({
        key: "entities", label: tabLabel("Entities", er?.entities.length ?? ner?.spans.length ?? 0),
        children: (
          <div className="drawer-body">
            {job.modules.includes("entity_resolution") && (
              <section><div className="section-title">Resolved entities <span className="muted">· click an id to find every row that mentions it</span></div>
                {rendererFor("resolved").detail(r.results["entity_resolution"], ctx("entity_resolution"))}</section>
            )}
            <section><div className="section-title">Mentions by type</div>{rendererFor("entities").detail(r.results["ner"], ctx("ner"))}</section>
          </div>
        ),
      });
    }
    if (job.modules.includes("relations")) {
      tabs.push({ key: "relations", label: tabLabel("Relations", rels?.relations.length ?? 0),
                  children: <div className="drawer-body">{rendererFor("relations").detail(r.results["relations"], ctx("relations"))}</div> });
    }
    if (job.modules.includes("fields")) {
      tabs.push({ key: "fields", label: tabLabel("Fields"),
                  children: <div className="drawer-body">{rendererFor("record").detail(r.results["fields"], ctx("fields"))}</div> });
    }
    if (job.modules.includes("event_coreference")) {
      tabs.push({ key: "event", label: tabLabel("Same event"),
                  children: <div className="drawer-body">{rendererFor("cluster").detail(r.results["event_coreference"], ctx("event_coreference"))}</div> });
    }
    for (const m of inJob.filter((m) => m.kind !== "label" && !["ner", "entity_resolution", "relations", "fields", "event_coreference"].includes(m.name))) {
      tabs.push({ key: m.name, label: tabLabel(m.title), children: <div className="drawer-body">{rendererFor(m.kind).detail(r.results[m.name], ctx(m.name))}</div> });
    }
  }
  const active = tabs.some((t) => t.key === tab) ? tab : "text";

  const nav = idx !== null && (
    <Space size={4}>
      <Tooltip title="Previous row"><Button size="small" icon={<LeftOutlined />} disabled={idx <= 0}
               onClick={() => onOpen(idx - 1)} aria-label="Previous row" /></Tooltip>
      <Tooltip title="Next row"><Button size="small" icon={<RightOutlined />} disabled={idx >= job.total - 1}
               onClick={() => onOpen(idx + 1)} aria-label="Next row" /></Tooltip>
    </Space>
  );

  return (
    <Drawer open={idx !== null} onClose={onClose} size={880} destroyOnHidden extra={nav}
            title={<span className="drawer-title">{r ? `Row ${r.id}` : "Row"}<span className="drawer-chips">{chips}</span></span>}>
      {row.error ? <ErrorAlert error={row.error} onRetry={() => row.refetch()} /> : !r ? <Skeleton active /> : (
        <Tabs activeKey={active} onChange={setTab} items={tabs} className="drawer-tabs" />
      )}
    </Drawer>
  );
}
