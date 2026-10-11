import { CopyOutlined } from "@ant-design/icons";
import { App, Button, Table, Tag, Tooltip } from "antd";
import { useState } from "react";
import type { EntitiesResult } from "../../api/types";
import { EvidenceButton, ResultEmpty, ResultSearch, useEvidence } from "./EvidenceView";

type Indicator = EntitiesResult["spans"][number] & { normalized?: string };
export function IndicatorDetail({ value }: { value: unknown }) {
  const r = value as EntitiesResult | null;
  const [search, setSearch] = useState("");
  const show = useEvidence();
  const { message } = App.useApp();
  if (!r?.spans.length) return <ResultEmpty description="No supported cyber indicators found in this document." />;
  const indicators = (r.spans as Indicator[]).filter((s) => `${s.label} ${s.text} ${s.normalized ?? ""}`.toLocaleLowerCase().includes(search.toLocaleLowerCase().trim()));
  return <div className="result-section"><div className="result-intro"><h3>Observable indicators</h3><p>Syntax matches extracted locally. An indicator's presence does not establish malicious activity.</p></div>
    <ResultSearch value={search} onChange={setSearch} placeholder="Search indicator values or types" count={indicators.length} unit="indicators" />
    <Table<Indicator> className="result-table" size="small" rowKey={(s) => `${s.start}:${s.label}`} dataSource={indicators} pagination={indicators.length > 10 ? { pageSize: 10, showSizeChanger: false } : false} scroll={{ x: 600 }} columns={[
      { title: "Type", dataIndex: "label", width: 85, render: (type: string) => <Tag>{type.toUpperCase()}</Tag> },
      { title: "As written", render: (_, s) => <EvidenceButton title={`${s.label.toUpperCase()} · ${s.text}`} values={[s.text]}><span className="mono indicator-value">{s.text}</span></EvidenceButton> },
      { title: "Normalized value", render: (_, s) => <span className="mono indicator-value">{s.normalized ?? s.text}</span> },
      { title: "", width: 40, render: (_, s) => <Tooltip title="Copy normalized value"><Button type="text" size="small" icon={<CopyOutlined />} aria-label={`Copy ${s.text}`} onClick={async (e) => { e.stopPropagation(); try { await navigator.clipboard.writeText(s.normalized ?? s.text); message.success("Indicator copied"); } catch { message.error("Could not copy indicator"); } }} /></Tooltip> },
    ]} onRow={(s) => ({ onClick: () => show(s.text, [s.text]), className: "result-clickable" })} />
    <p className="muted small">Select an indicator to highlight its original spelling. Normalization restores defanged separators; no links are opened.</p>
  </div>;
}
