import { ApartmentOutlined, ExclamationCircleOutlined, NodeIndexOutlined, TeamOutlined, WarningOutlined } from "@ant-design/icons";
import { Card, Skeleton, Tag } from "antd";
import type { ReactNode } from "react";

import type { JobSnapshot, JobSummary, ModuleInfo, ModuleSummary } from "../../api/types";
import { humanize, num } from "../../lib/format";
import { entityColor, labelColor, labelOrder, labelText, labelTone } from "../../lib/labels";
import { BarList } from "../common/BarList";
import { ErrorAlert } from "../common/ErrorAlert";

const TONE_COLOR = { danger: "var(--danger)", warning: "var(--warning)", success: "var(--success)", neutral: "var(--text-3)" };

export type Filter = [string, string];

interface Props {
  job: JobSnapshot;
  summary: JobSummary | undefined;
  error: unknown;
  modules: ModuleInfo[];
  onFilter: (f: Filter) => void;
  onReview: () => void;
  onErrors: () => void;
  onOpenRow: (idx: number) => void;
}

function Kpi({ icon, label, value, onClick, tone }: {
  icon: ReactNode; label: string; value: ReactNode; onClick?: () => void; tone?: "warning" | "danger";
}) {
  return (
    <button type="button" className={`kpi${tone ? ` kpi-${tone}` : ""}`} onClick={onClick} disabled={!onClick}>
      <span className="kpi-icon">{icon}</span>
      <span className="kpi-value">{value}</span>
      <span className="kpi-label">{label}</span>
    </button>
  );
}

/** One card per module, shaped by its kind: the job at a glance, every bar a filter. */
function ModuleCard({ m, s, job, modules, onFilter, onOpenRow }: {
  m: ModuleInfo; s: ModuleSummary; job: JobSnapshot; modules: ModuleInfo[];
  onFilter: (f: Filter) => void; onOpenRow: (idx: number) => void;
}) {
  let body: ReactNode = null;
  let extra: ReactNode = s.needs_review ? <Tag color="warning" variant="filled">{s.needs_review} to review</Tag> : null;

  if (m.kind === "label") {
    const order = labelOrder(m);
    const bars = Object.entries(s.counts ?? {}).map(([k, v]) => {
      const tone = labelTone(m.name, k);
      return { key: k, label: labelText(m, k), value: v, hint: m.labels?.[k],
               color: tone ? TONE_COLOR[tone] : labelColor(k, order) };
    });
    body = <BarList bars={bars} total={bars.reduce((a, b) => a + b.value, 0)} onSelect={(k) => onFilter([m.name, k])} />;
  } else if (m.kind === "entities") {
    const bars = Object.entries(s.counts ?? {}).map(([k, v]) => ({ key: k, label: k, value: v, color: entityColor(k, modules) }));
    body = <BarList bars={bars} onSelect={(k) => onFilter([m.name, k])} />;
  } else if (m.kind === "resolved") {
    extra = <span className="muted small">{num(s.entities ?? 0)} distinct</span>;
    body = (
      <ul className="top-entities">
        {(s.top ?? []).slice(0, 10).map((e) => (
          <li key={e.id}>
            <button type="button" onClick={() => onFilter([m.name, e.id])}>
              <span className="dot" style={{ background: entityColor(e.label, modules) }} />
              <span className="te-name">{e.name}</span>
              <span className="muted small">{e.label}</span>
              <span className="te-count">{e.rows} {e.rows === 1 ? "row" : "rows"}</span>
            </button>
          </li>
        ))}
      </ul>
    );
  } else if (m.kind === "relations") {
    const bars = Object.entries(s.counts ?? {}).map(([k, v]) => ({ key: k, label: humanize(k), value: v, hint: m.labels?.[k] }));
    body = bars.length ? <BarList bars={bars} onSelect={(k) => onFilter([m.name, k])} />
                       : <span className="muted">No relations stated yet.</span>;
  } else if (m.kind === "cluster") {
    const clusters = s.clusters ?? [];
    extra = <span className="muted small">{s.pairs_checked ?? 0} pairs checked</span>;
    body = clusters.length ? (
      <ul className="clusters">
        {clusters.slice(0, 8).map((c) => (
          <li key={c.id}>
            <button type="button" onClick={() => onFilter([m.name, c.id])}>
              <span className="pill mono">{c.id}</span>
              <span className="cluster-title">{c.title}</span>
              <span className="muted small">{c.event ? humanize(c.event) : ""} · {c.size} rows</span>
            </button>
          </li>
        ))}
      </ul>
    ) : <span className="muted">{job.progress[m.name]?.done ? "No event is reported by more than one row." : "Runs once events and entities are done."}</span>;
  }

  return (
    <Card size="small" className="module-card" title={m.title} extra={extra}>
      {s.errors > 0 && <div className="text-danger small" style={{ marginBottom: 8 }}>{s.errors} rows failed</div>}
      {body}
      {m.kind === "cluster" && (s.clusters?.length ?? 0) > 0 && (
        <div className="small muted" style={{ marginTop: 8 }}>
          Biggest group starts at <button type="button" className="link-btn"
            onClick={() => onOpenRow(s.clusters![0].rows[0])}>row {s.clusters![0].ids[0]}</button>
        </div>
      )}
    </Card>
  );
}

export function Overview({ job, summary, error, modules, onFilter, onReview, onErrors, onOpenRow }: Props) {
  if (error && !summary) return <ErrorAlert error={error} />;
  if (!summary) return <Skeleton active />;
  const inJob = modules.filter((m) => job.modules.includes(m.name));
  const er = summary.modules["entity_resolution"];
  const co = summary.modules["event_coreference"];
  // Wide cards (lists) first-class; label distributions fill the grid.
  const order = [...inJob].sort((a, b) => Number(b.kind === "resolved" || b.kind === "cluster") - Number(a.kind === "resolved" || a.kind === "cluster"));

  return (
    <div className="overview">
      <div className="kpis">
        <Kpi icon={<NodeIndexOutlined />} label="rows" value={num(job.total)} />
        <Kpi icon={<WarningOutlined />} label="need review" value={num(summary.needs_review)}
             tone={summary.needs_review ? "warning" : undefined} onClick={summary.needs_review ? onReview : undefined} />
        <Kpi icon={<ExclamationCircleOutlined />} label="with errors" value={num(job.failed_rows)}
             tone={job.failed_rows ? "danger" : undefined} onClick={job.failed_rows ? onErrors : undefined} />
        {er && <Kpi icon={<TeamOutlined />} label="distinct entities" value={num(er.entities ?? 0)} />}
        {co && <Kpi icon={<ApartmentOutlined />} label="multi-report events" value={num(co.clusters?.length ?? 0)} />}
      </div>
      <div className="card-grid">
        {order.map((m) => summary.modules[m.name] && (
          <ModuleCard key={m.name} m={m} s={summary.modules[m.name]} job={job} modules={modules}
                      onFilter={onFilter} onOpenRow={onOpenRow} />
        ))}
      </div>
    </div>
  );
}
