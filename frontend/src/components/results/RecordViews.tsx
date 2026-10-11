import { Tooltip } from "antd";
import { memo } from "react";

import { humanize, pct } from "../../lib/format";

type Value = { text: string; confidence: number | null };
type Records = Record<string, Record<string, Value | Value[]>[]>;

const list = (v: Value | Value[]) => (Array.isArray(v) ? v : [v]);

/** Table cell: the first record's fields, compactly. Preview is {record, fields: {name: text | [text]}, count}. */
function FieldsCellInner({ value }: { value: unknown }) {
  const p = value as { record: string; fields: Record<string, string | string[]>; count: number } | null;
  if (!p) return <span className="muted">–</span>;
  const entries = Object.entries(p.fields);
  return (
    <Tooltip title={<div>{entries.map(([k, v]) => <div key={k}><b>{humanize(k)}:</b> {Array.isArray(v) ? v.join(", ") : v}</div>)}</div>}>
      <span className="cell-ellipsis">
        {entries.slice(0, 2).map(([k, v]) => <span key={k} className="field-pair"><span className="muted">{humanize(k)}</span> {Array.isArray(v) ? v[0] : v}</span>)}
        {entries.length > 2 && <span className="muted"> +{entries.length - 2}</span>}
      </span>
    </Tooltip>
  );
}

/** Drawer: each record as a definition list; every value is a span of the text, with its score. */
function FieldsDetailInner({ value }: { value: unknown }) {
  const recs = value as Records | null;
  if (!recs || !Object.keys(recs).length) return <span className="muted">No field found in this text.</span>;
  return (
    <div className="records">
      {Object.entries(recs).map(([rec, instances]) => instances.map((inst, i) => (
        <div key={`${rec}${i}`} className="record">
          <div className="record-title">{humanize(rec)}{instances.length > 1 ? ` ${i + 1}` : ""}</div>
          <dl className="record-fields">
            {Object.entries(inst).map(([k, v]) => (
              <div key={k} className="record-row">
                <dt>{humanize(k)}</dt>
                <dd>{list(v).map((x, j) => (
                  <span key={j} className="record-value" title={x.confidence != null ? `${pct(x.confidence)} confident` : undefined}>
                    {x.text}{x.confidence != null && x.confidence < 0.3 && <span className="record-low"> low</span>}
                  </span>
                ))}</dd>
              </div>
            ))}
          </dl>
        </div>
      )))}
    </div>
  );
}

export const FieldsCell = memo(FieldsCellInner);
export const FieldsDetail = memo(FieldsDetailInner);
