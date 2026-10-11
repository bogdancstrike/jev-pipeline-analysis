import { ApartmentOutlined, ExclamationCircleOutlined, NodeIndexOutlined, TeamOutlined, WarningOutlined } from "@ant-design/icons";
import { Card, Skeleton, Tag } from "antd";
import { memo, type ReactNode } from "react";

import type { JobSnapshot, JobSummary, ModuleInfo, ModuleSummary } from "../../api/types";
import { humanize, num } from "../../lib/format";
import { entityColor, labelColor, labelOrder, labelText, labelTone } from "../../lib/labels";
import { BarList } from "../common/BarList";
import { ErrorAlert } from "../common/ErrorAlert";
import { StatRow, StatTile } from "../ui/StatTile";

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

/** One card per module, shaped by its kind: the job at a glance, every bar a filter. */
const ModuleCard = memo(function ModuleCard({ m, s, progressDone, modules, onFilter, onOpenRow }: {
  m: ModuleInfo; s: ModuleSummary; progressDone: number; modules: ModuleInfo[];
  onFilter: (f: Filter) => void; onOpenRow: (idx: number) => void;
}) {
  let body: ReactNode = null;
  const wide = m.kind === "resolved" || m.kind === "cluster";
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
    body = !(s.top ?? []).length ? <span className="muted">No entity resolved yet.</span> : (
      <ul className="top-entities top-entities-2col">
        {(s.top ?? []).slice(0, 16).map((e) => (
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
  } else if (m.kind === "record") {
    const bars = Object.entries(s.counts ?? {}).map(([k, v]) => ({ key: k, label: humanize(k), value: v, hint: `rows where "${k}" was found` }));
    body = bars.length ? <BarList bars={bars} onSelect={(k) => onFilter([m.name, k])} />
                       : <span className="muted">No field found yet.</span>;
    extra = <span className="muted small">rows with each field</span>;
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
    ) : <span className="muted">{progressDone ? "No event is reported by more than one row." : "Runs once events and entities are done."}</span>;
  }

  return (
    <Card size="small" className={`module-card${wide ? " card-wide" : ""}`} title={m.title} extra={extra}>
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
});

const SECTIONS: { title: string; hint: string; kinds: string[]; grid: string }[] = [
  { title: "Classification", hint: "one answer per row; click a bar to see those rows", kinds: ["label"], grid: "grid-labels" },
  { title: "Entities & relations", hint: "who and what the texts mention", kinds: ["resolved", "entities", "relations"], grid: "grid-entities" },
  { title: "Structured fields", hint: "facts pulled from the text", kinds: ["record"], grid: "grid-entities" },
  { title: "Events", hint: "the same event, reported by several rows", kinds: ["cluster"], grid: "grid-entities" },
];

export function Overview({ job, summary, error, modules, onFilter, onReview, onErrors, onOpenRow }: Props) {
  if (error && !summary) return <ErrorAlert error={error} />;
  if (!summary) return <Skeleton active />;
  const inJob = modules.filter((m) => job.modules.includes(m.name));
  const er = summary.modules["entity_resolution"];
  const co = summary.modules["event_coreference"];

  return (
    <div className="overview">
      <StatRow>
        <StatTile icon={<NodeIndexOutlined />} label="Records" value={num(job.total)} />
        <StatTile icon={<WarningOutlined />} label="Need review" value={num(summary.needs_review)}
                  tone={summary.needs_review ? "warning" : "default"} hint={summary.needs_review ? "low-confidence answers · open" : "none"}
                  onClick={summary.needs_review ? onReview : undefined} />
        <StatTile icon={<ExclamationCircleOutlined />} label="With errors" value={num(job.failed_rows)}
                  tone={job.failed_rows ? "danger" : "default"} hint={job.failed_rows ? "open" : "none"} onClick={job.failed_rows ? onErrors : undefined} />
        {er && <StatTile icon={<TeamOutlined />} label="Distinct entities" value={num(er.entities ?? 0)} hint="after resolution" />}
        {co && <StatTile icon={<ApartmentOutlined />} label="Multi-report events" value={num(co.clusters?.length ?? 0)} hint="same event, several rows" />}
      </StatRow>
      {SECTIONS.map((sec) => {
        const items = inJob.filter((m) => sec.kinds.includes(m.kind) && summary.modules[m.name]);
        if (!items.length) return null;
        return (
          <section key={sec.title} className="ov-section">
            <h3 className="ov-heading">{sec.title}<span className="muted"> · {sec.hint}</span></h3>
            <div className={`card-grid ${sec.grid}`}>
              {items.map((m) => (
                <ModuleCard key={m.name} m={m} s={summary.modules[m.name]} progressDone={job.progress[m.name]?.done ?? 0}
                            modules={modules} onFilter={onFilter} onOpenRow={onOpenRow} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
