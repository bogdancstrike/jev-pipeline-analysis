import { Table, Tag, Tooltip } from "antd";
import { useState } from "react";
import { EvidenceButton, ResultEmpty, ResultSearch, useEvidence } from "./EvidenceView";

type DateValue = { text: string; confidence: number | null };
interface DateRecord { text?: DateValue; normalized?: DateValue; status?: DateValue; reference?: DateValue }
const statuses: Record<string, { label: string; color?: string; hint: string }> = {
  normalized: { label: "Normalized", color: "success", hint: "Resolved to an ISO calendar date" },
  missing_reference: { label: "Needs reference date", color: "warning", hint: "Provide published_at, publication_date or date in the CSV, or a reference date in Admin" },
  unrecognized: { label: "Unrecognized", hint: "Found a date expression, but could not parse it" },
};
export function TemporalDetail({ value }: { value: unknown }) {
  const r = value as { dates?: DateRecord[] } | null;
  const [search, setSearch] = useState("");
  const show = useEvidence();
  if (!r?.dates?.length) return <ResultEmpty description="No supported date expressions found. English and Romanian dates are supported." />;
  const dates = r.dates.map((date, idx) => ({ ...date, key: idx })).filter((date) => [date.text, date.normalized, date.status, date.reference].some((v) => v?.text.toLocaleLowerCase().includes(search.toLocaleLowerCase().trim())));
  return <div className="result-section"><div className="result-intro"><h3>Dates in context</h3><p>Relative dates use the document's publication date or the configured reference date. Missing anchors stay unresolved.</p></div>
    <ResultSearch value={search} onChange={setSearch} placeholder="Search date expressions or normalized dates" count={dates.length} unit="expressions" />
    <Table className="result-table" size="small" rowKey="key" dataSource={dates} pagination={dates.length > 10 ? { pageSize: 10, showSizeChanger: false } : false} scroll={{ x: 560 }} columns={[
      { title: "As written", render: (_, date) => <EvidenceButton title={date.text?.text ?? "Date expression"} values={[date.text?.text ?? ""]}>{date.text?.text ?? "—"}</EvidenceButton> },
      { title: "Calendar date", render: (_, date) => <span className="mono">{date.normalized?.text ?? "—"}</span> },
      { title: "Status", render: (_, date) => { const s = statuses[date.status?.text ?? ""] ?? { label: date.status?.text ?? "Unknown", hint: "", color: undefined }; return <Tooltip title={s.hint}><Tag color={s.color}>{s.label}</Tag></Tooltip>; } },
      { title: "Reference date", render: (_, date) => <span className="muted mono small">{date.reference?.text ?? "Not supplied"}</span> },
    ]} onRow={(date) => ({ onClick: () => show(date.text?.text ?? "Date expression", [date.text?.text ?? ""]), className: "result-clickable" })} />
    <p className="muted small">Select an expression to highlight it in the original document. Dates are normalized locally without an LLM fallback.</p>
  </div>;
}
