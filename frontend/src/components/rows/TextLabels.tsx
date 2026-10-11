import { CopyOutlined, FilterOutlined } from "@ant-design/icons";
import { App, Button, Empty, Progress, Select, Switch, Table, Tag, Tooltip } from "antd";
import { useState } from "react";

import type { LabelResult, ModuleInfo, RowDetail, Span, ResolvedEntity } from "../../api/types";
import { humanize, num, pct } from "../../lib/format";
import { LabelDetail, LabelTag } from "../results/LabelView";
import { HighlightedText } from "./HighlightedText";

export function TextLabels({ row, labels, modules, spans, resolved, onFilter }: {
  row: RowDetail; labels: ModuleInfo[]; modules: ModuleInfo[]; spans: Span[]; resolved: ResolvedEntity[];
  onFilter: (module: string, value: string) => void;
}) {
  const [highlights, setHighlights] = useState(true);
  const [hiddenTypes, setHiddenTypes] = useState<string[]>(["number"]);
  const { message } = App.useApp();
  const completed = labels.filter((m) => row.results[m.name]);
  const ordered = [...labels].sort((a, b) => Number(row.review.includes(b.name)) - Number(row.review.includes(a.name)));
  const types = [...new Set(spans.map((span) => span.label))];
  const visible = spans.filter((span) => !hiddenTypes.includes(span.label));
  return <div className="document-layout">
    <section className="document-reading" aria-label="Document text">
      <div className="document-toolbar"><div><strong>Document text</strong><span className="muted small">{num(row.text.trim() ? row.text.trim().split(/\s+/u).length : 0)} words · {num(row.text.length)} characters</span></div>
        <Button size="small" icon={<CopyOutlined />} onClick={async () => {
          try { await navigator.clipboard.writeText(row.text); message.success("Document text copied"); }
          catch { message.error("Could not copy. Select the text and copy it manually."); }
        }}>Copy text</Button></div>
      {spans.length > 0 && <div className="document-highlights"><div><label htmlFor="document-highlights">Entity highlights</label><Switch id="document-highlights" size="small" checked={highlights} onChange={setHighlights} /></div>
        <Select mode="multiple" maxTagCount="responsive" aria-label="Entity types to highlight" placeholder="Choose entity types" disabled={!highlights} value={types.filter((type) => !hiddenTypes.includes(type))}
          options={types.map((type) => ({ value: type, label: `${humanize(type)} (${spans.filter((span) => span.label === type).length})` }))}
          onChange={(selected) => setHiddenTypes(types.filter((type) => !selected.includes(type)))} /></div>}
      <div className="document-scroll" tabIndex={0} aria-label="Scrollable document text"><HighlightedText text={row.text} spans={highlights ? visible : []} resolved={resolved} modules={modules} /></div>
    </section>
    <section className="document-results" aria-label="Classification results">
      <div className="document-result-heading"><h3>Labels</h3><span className="muted small">{completed.length} / {labels.length} ready</span></div>
      <p className="muted small">Expand a task to compare alternatives. Probabilities are model scores, not verified accuracy.</p>
      {ordered.length ? <Table<ModuleInfo> className="result-table label-results-table" size="small" rowKey="name" dataSource={ordered} pagination={false} scroll={{ x: 480 }} columns={[
        { title: "Task", width: "32%", render: (_, m) => <div className="label-task-name"><strong>{m.title}</strong>{row.review.includes(m.name) && <Tag color="warning">Review</Tag>}</div> },
        { title: "Label", render: (_, m) => { const r = row.results[m.name] as LabelResult | null; return r ? <LabelTag module={m} label={r.label} /> : <span className="muted small">{row.errors[m.name] ? "Failed" : "No result"}</span>; } },
        { title: "Probability", width: 125, align: "right", render: (_, m) => { const r = row.results[m.name] as LabelResult | null; return r ? <Tooltip title={row.review.includes(m.name) ? "This result needs review" : "Model confidence for the selected label"}><div className="label-probability"><span className={row.review.includes(m.name) ? "conf-low" : ""}>{pct(r.confidence)}</span><Progress percent={Math.round(r.confidence * 100)} size="small" showInfo={false} strokeColor={row.review.includes(m.name) ? "var(--warning)" : "var(--accent)"} /></div></Tooltip> : <span className="muted">—</span>; } },
      ]} expandable={{ rowExpandable: (m) => !!row.results[m.name], expandedRowRender: (m) => <div className="document-label-detail"><LabelDetail value={row.results[m.name]} module={m} /><Button size="small" type="link" icon={<FilterOutlined />} onClick={() => onFilter(m.name, (row.results[m.name] as LabelResult).label)}>Find documents with this label</Button></div> }} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No classification tasks in this run" />}
    </section>
  </div>;
}
