import { CopyOutlined, FilterOutlined } from "@ant-design/icons";
import { App, Button, Collapse, Empty, Switch, Tag, Tooltip } from "antd";
import { useState } from "react";

import type { LabelResult, ModuleInfo, RowDetail, Span, ResolvedEntity } from "../../api/types";
import { num, pct } from "../../lib/format";
import { LabelDetail, LabelTag } from "../results/LabelView";
import { HighlightedText } from "./HighlightedText";

export function TextLabels({ row, labels, modules, spans, resolved, onFilter }: {
  row: RowDetail; labels: ModuleInfo[]; modules: ModuleInfo[]; spans: Span[]; resolved: ResolvedEntity[];
  onFilter: (module: string, value: string) => void;
}) {
  const [highlights, setHighlights] = useState(true);
  const { message } = App.useApp();
  const completed = labels.filter((m) => row.results[m.name]);
  const ordered = [...labels].sort((a, b) => Number(row.review.includes(b.name)) - Number(row.review.includes(a.name)));
  const types = [...new Set(spans.map((span) => span.label))];
  return <div className="document-layout">
    <section className="document-reading" aria-label="Document text">
      <div className="document-toolbar"><div><strong>Document text</strong><span className="muted small">{num(row.text.trim() ? row.text.trim().split(/\s+/u).length : 0)} words · {num(row.text.length)} characters</span></div>
        <Tooltip title="Copy original text"><Button size="small" icon={<CopyOutlined />} aria-label="Copy document text" onClick={async () => {
          try { await navigator.clipboard.writeText(row.text); message.success("Document text copied"); }
          catch { message.error("Could not copy. Select the text and copy it manually."); }
        }} /></Tooltip></div>
      {spans.length > 0 && <div className="document-highlights"><label htmlFor="document-highlights">Entity highlights <span className="muted">· {spans.length} mentions</span></label><Switch id="document-highlights" size="small" checked={highlights} onChange={setHighlights} /></div>}
      <div className="document-scroll" tabIndex={0} aria-label="Scrollable document text"><HighlightedText text={row.text} spans={highlights ? spans : []} resolved={resolved} modules={modules} /></div>
      {highlights && types.length > 0 && <div className="document-legend"><span className="muted small">Entity types</span>{types.map((type) => <Tag key={type}>{type}</Tag>)}</div>}
    </section>
    <section className="document-results" aria-label="Classification results">
      <div className="document-result-heading"><h3>Labels</h3><span className="muted small">{completed.length} / {labels.length} ready</span></div>
      <p className="muted small">Expand a task for alternatives. Use the filter to find similar documents.</p>
      {ordered.length ? <Collapse size="small" ghost items={ordered.map((m) => {
        const result = row.results[m.name] as LabelResult | null;
        const review = row.review.includes(m.name);
        return { key: m.name, label: <div className="document-label-summary"><div><strong>{m.title}</strong>{review && <span className="document-review">Review</span>}</div>
          {result ? <div><LabelTag module={m} label={result.label} compact /><span className={review ? "conf conf-low" : "conf"}>{pct(result.confidence)}</span></div> : <span className="muted small">{row.errors[m.name] ? "Failed" : "Awaiting result"}</span>}</div>,
          children: <div className="document-label-detail"><LabelDetail value={result} module={m} />{result && <Button size="small" type="link" icon={<FilterOutlined />} onClick={() => onFilter(m.name, result.label)}>Filter by this label</Button>}</div> };
      })} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No classification tasks in this run" />}
    </section>
  </div>;
}
