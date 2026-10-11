import { Table, Tooltip } from "antd";
import { memo, useState } from "react";
import { humanize, pct } from "../../lib/format";
import { EvidenceButton, ResultEmpty, ResultSearch, useEvidence } from "./EvidenceView";

type Value = { text: string; confidence: number | null };
type Records = Record<string, Record<string, Value | Value[]>[]>;
const list = (v: Value | Value[]) => Array.isArray(v) ? v : [v];

function FieldsCellInner({ value }: { value: unknown }) {
  const p = value as { record: string; fields: Record<string, string | string[]>; count: number } | null;
  if (!p) return <span className="muted">–</span>;
  const entries = Object.entries(p.fields);
  return <Tooltip title={<div>{entries.map(([k, v]) => <div key={k}><b>{humanize(k)}:</b> {Array.isArray(v) ? v.join(", ") : v}</div>)}</div>}><span className="cell-ellipsis">{entries.slice(0, 2).map(([k, v]) => <span key={k} className="field-pair"><span className="muted">{humanize(k)}</span> {Array.isArray(v) ? v[0] : v}</span>)}{entries.length > 2 && <span className="muted"> +{entries.length - 2}</span>}</span></Tooltip>;
}
function FieldsDetailInner({ value }: { value: unknown }) {
  const recs = value as Records | null;
  const [search, setSearch] = useState("");
  const show = useEvidence();
  const all = Object.entries(recs ?? {}).flatMap(([record, instances]) => instances.flatMap((instance, idx) => Object.entries(instance).flatMap(([field, values]) => list(values).filter((v) => v?.text).map((v, n) => ({ ...v, record, instance: idx + 1, field, key: `${record}:${idx}:${field}:${n}` })))));
  if (!all.length) return <ResultEmpty description="No configured structured fields found in this document." />;
  const rows = all.filter((r) => `${r.record} ${r.field} ${r.text}`.toLocaleLowerCase().includes(search.toLocaleLowerCase().trim()));
  const instances = new Set(all.map((r) => `${r.record}:${r.instance}`));
  return <div className="result-section"><div className="result-intro"><h3>Extracted fields</h3><p>Values extracted from this document, organized by field. Select a value to check its source.</p></div>
    <ResultSearch value={search} onChange={setSearch} placeholder="Search field names or values" count={rows.length} unit="values" />
    <Table className="result-table" size="small" rowKey="key" dataSource={rows} pagination={rows.length > 12 ? { pageSize: 12, showSizeChanger: false } : false} scroll={{ x: 450 }} columns={[
      ...(instances.size > 1 ? [{ title: "Record", key: "record", width: 130, render: (_: unknown, r: typeof rows[number]) => `${humanize(r.record)} ${r.instance}` }] : []),
      { title: "Field", width: 160, render: (_, r) => <span className="muted">{humanize(r.field)}</span> },
      { title: "Value", render: (_, r) => <EvidenceButton title={humanize(r.field)} values={[r.text]}>{r.text}</EvidenceButton> },
      { title: "Confidence", width: 95, align: "right", render: (_, r) => r.confidence == null ? <Tooltip title="No model confidence supplied">—</Tooltip> : pct(r.confidence) },
    ]} onRow={(r) => ({ onClick: () => show(humanize(r.field), [r.text]), className: "result-clickable" })} />
  </div>;
}
export const FieldsCell = memo(FieldsCellInner);
export const FieldsDetail = memo(FieldsDetailInner);
