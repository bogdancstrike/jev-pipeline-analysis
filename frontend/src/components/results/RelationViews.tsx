import { memo, useState } from "react";
import { ArrowRightOutlined, FilterOutlined, ReadOutlined } from "@ant-design/icons";
import { useQueries } from "@tanstack/react-query";
import { Button, Collapse, Pagination, Skeleton, Table, Tag, Tooltip } from "antd";

import { api } from "../../api/endpoints";
import type { ClusterResult, ModuleInfo, Relation } from "../../api/types";
import { keys } from "../../hooks/queries";
import { humanize, pct } from "../../lib/format";
import { EvidenceButton, ResultEmpty, ResultSearch, useEvidence } from "./EvidenceView";
import { RelationGraph } from "./RelationGraph";

function Triple({ r }: { r: Pick<Relation, "head" | "relation" | "tail"> }) {
  return <span className="triple"><span className="triple-ent">{r.head}</span><span className="triple-rel">{humanize(r.relation)} <ArrowRightOutlined /></span><span className="triple-ent">{r.tail}</span></span>;
}
function RelationsCellInner({ value }: { value: unknown }) {
  const rels = (value as Relation[] | null) ?? [];
  if (!rels.length) return <span className="muted">–</span>;
  return <Tooltip title={<div>{rels.map((r, i) => <div key={i}>{r.head} · {humanize(r.relation)} · {r.tail}</div>)}</div>}><span className="cell-ellipsis"><Triple r={rels[0]} />{rels.length > 1 && <span className="muted"> +{rels.length - 1}</span>}</span></Tooltip>;
}
function RelationsDetailInner({ value, modules }: { value: unknown; modules: ModuleInfo[] }) {
  const rels = ((value as { relations?: Relation[] } | null)?.relations) ?? [];
  const [search, setSearch] = useState("");
  const show = useEvidence();
  if (!rels.length) return <ResultEmpty description="No supported relationship found between entities in this document." />;
  const rows = rels.map((r, i) => ({ ...r, key: i })).filter((r) => `${r.head} ${r.relation} ${humanize(r.relation)} ${r.tail} ${r.evidence ?? ""}`.toLocaleLowerCase().includes(search.toLocaleLowerCase().trim()));
  const evidence = (r: Relation) => r.evidence ? [r.evidence, r.head, r.tail] : [r.head, r.tail];
  return <div className="result-section"><div className="result-intro"><h3>Relationships in this document</h3><p>Read each row from source to target. Select a relationship to highlight its supporting text.</p></div>
    <ResultSearch value={search} onChange={setSearch} placeholder="Search entities or relationships" count={rows.length} unit="relationships" />
    <Table className="result-table" size="small" rowKey="key" dataSource={rows} pagination={rows.length > 10 ? { pageSize: 10, showSizeChanger: false } : false} scroll={{ x: 530 }} columns={[
      { title: "Source", render: (_, r) => <EvidenceButton title={`${r.head} → ${r.tail}`} values={evidence(r)}><strong>{r.head}</strong></EvidenceButton> },
      { title: "Relationship →", render: (_, r) => <span className="triple-rel">{humanize(r.relation)}</span> },
      { title: "Target", dataIndex: "tail" },
      { title: "Confidence", width: 95, align: "right", render: (_, r) => pct(r.confidence) },
    ]} onRow={(r) => ({ onClick: () => show(`${r.head} → ${r.tail}`, evidence(r)), className: "result-clickable" })}
      expandable={{ rowExpandable: (r) => !!r.evidence, expandedRowRender: (r) => <EvidenceButton title="Relationship evidence" values={evidence(r)}><blockquote className="result-quote">{r.evidence}</blockquote></EvidenceButton> }} />
    <Collapse className="result-graph" items={[{ key: "graph", label: "Relationship map", children: <RelationGraph relations={rows} modules={modules} /> }]} />
  </div>;
}
function ClusterCellInner({ value }: { value: unknown }) {
  const c = value as ClusterResult | null;
  if (!c) return <span className="muted">–</span>;
  return <Tag>{c.size} related reports</Tag>;
}
function ClusterDetailInner({ value, jobId, onOpenRow, onFilter }: { value: unknown; jobId?: string; onOpenRow?: (idx: number) => void; onFilter?: (value: string) => void }) {
  const c = value as ClusterResult | null;
  const [page, setPage] = useState(1);
  const peers = (c?.peers ?? []).slice((page - 1) * 5, page * 5);
  const reports = useQueries({ queries: peers.map((idx) => ({ queryKey: keys.row(jobId ?? "", idx), queryFn: ({ signal }: { signal: AbortSignal }) => api.row(jobId!, idx, signal), enabled: !!jobId, staleTime: 30_000 })) });
  if (!c) return <ResultEmpty description="No matching report was found by the current event-matching settings. This does not establish that the event is unique." />;
  return <div className="result-section"><div className="event-group-heading"><div className="result-intro"><h3>{c.size} reports about the same event</h3><p>This document was grouped with {c.size - 1} other report{c.size === 2 ? "" : "s"} describing the same incident. Compare the excerpts below to check the people, place and time.</p></div>
    {onFilter && <Button icon={<FilterOutlined />} onClick={() => onFilter(c.cluster)}>View this group</Button>}</div>
    <p className="muted small">Reports can be linked through other members of the group. Open a report to read its full text and analysis.</p>
    <div className="related-reports">{peers.map((idx, i) => <article key={idx} className="related-report">
      {reports[i]?.isPending ? <Skeleton active paragraph={{ rows: 2 }} title={false} /> : reports[i]?.error ? <div className="muted">Could not load this report. <Button size="small" onClick={() => reports[i].refetch()}>Retry</Button></div> : <>
        <div className="related-report-heading"><strong>Related report {(page - 1) * 5 + i + 1}</strong><Button type="link" size="small" icon={<ReadOutlined />} onClick={() => onOpenRow?.(idx)}>Open report</Button></div>
        <button type="button" className="report-excerpt" onClick={() => onOpenRow?.(idx)}>{reports[i]?.data?.text.slice(0, 420) || "Open this report to read its text"}{(reports[i]?.data?.text.length ?? 0) > 420 ? "…" : ""}</button>
      </>}
    </article>)}</div>
    {(c.peers?.length ?? 0) > 5 && <Pagination current={page} pageSize={5} total={c.peers!.length} onChange={setPage} showSizeChanger={false} size="small" />}
  </div>;
}
export const RelationsCell = memo(RelationsCellInner);
export const ClusterCell = memo(ClusterCellInner);
export const RelationsDetail = memo(RelationsDetailInner);
export const ClusterDetail = memo(ClusterDetailInner);
