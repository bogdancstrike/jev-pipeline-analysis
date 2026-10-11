import { FilterOutlined } from "@ant-design/icons";
import { Button, Space, Table, Tag, Tooltip } from "antd";
import { memo, useState } from "react";

import type { EntitiesResult, ModuleInfo, ResolvedResult, Span } from "../../api/types";
import { humanize, pct } from "../../lib/format";
import { entityColor } from "../../lib/labels";
import { EvidenceButton, ResultEmpty, ResultSearch, useEvidence } from "./EvidenceView";

function TagRow({ items, modules, max, interactive = false }: {
  items: { key: string; text: string; label: string; hint?: string }[]; modules: ModuleInfo[]; max?: number; interactive?: boolean;
}) {
  if (!items.length) return <span className="muted">none</span>;
  return <Space size={[4, 6]} wrap>{(max ? items.slice(0, max) : items).map((e) => {
    const tag = <Tag variant="outlined" color={entityColor(e.label, modules)} style={{ marginInlineEnd: 0 }}>{e.text}</Tag>;
    return <Tooltip key={e.key} title={e.hint ?? (interactive ? "Highlight in source text" : e.label)} mouseEnterDelay={0.3}>
      {interactive ? <EvidenceButton title={`${humanize(e.label)} · ${e.text}`} values={[e.text]}>{tag}</EvidenceButton> : tag}
    </Tooltip>;
  })}{max && items.length > max && <span className="muted small">+{items.length - max} · expand to see all</span>}</Space>;
}

function EntitiesCellInner({ value, modules }: { value: unknown; modules: ModuleInfo[] }) {
  const groups = (value as Record<string, string[]> | null) ?? {};
  return <TagRow items={Object.entries(groups).flatMap(([label, vs]) => vs.map((v) => ({ key: `${label}:${v}`, text: v, label })))} modules={modules} max={4} />;
}

function EntitiesDetailInner({ value, modules }: { value: unknown; modules: ModuleInfo[] }) {
  const r = value as EntitiesResult | null;
  const [search, setSearch] = useState("");
  const show = useEvidence();
  if (!r?.spans.length) return <ResultEmpty description="No entity mentions found in this document." />;
  const query = search.toLocaleLowerCase().trim();
  const spans = r.spans.filter((s) => `${s.label} ${s.text}`.toLocaleLowerCase().includes(query));
  const groups = Object.entries(r.groups).map(([label, values]) => ({ label, values: values.filter((v) => `${label} ${v}`.toLocaleLowerCase().includes(query)), spans: spans.filter((s) => s.label === label) })).filter((g) => g.spans.length);
  return <div className="result-section">
    <ResultSearch value={search} onChange={setSearch} placeholder="Search mentions or entity types" count={spans.length} unit="mentions" />
    <Table className="result-table" size="small" rowKey="label" dataSource={groups} pagination={false} scroll={{ x: 460 }} locale={{ emptyText: "No mentions match your search" }} columns={[
      { title: "Type", width: 140, render: (_, g) => <span className="kv-key"><span className="dot" style={{ background: entityColor(g.label, modules) }} />{humanize(g.label)}</span> },
      { title: "Mentions", render: (_, g) => <TagRow items={g.values.map((v) => ({ key: v, text: v, label: g.label }))} modules={modules} max={12} interactive /> },
      { title: "Count", width: 65, align: "right", render: (_, g) => g.spans.length },
    ]} expandable={{ expandedRowRender: (g) => <Table<Span> size="small" rowKey={(s) => `${s.start}:${s.end}:${s.label}`} dataSource={g.spans} pagination={g.spans.length > 10 ? { pageSize: 10, showSizeChanger: false } : false} columns={[
      { title: "Mention", render: (_, s) => <EvidenceButton title={s.text} values={[s.text]}>{s.text}</EvidenceButton> },
      { title: "Confidence / check", width: 160, render: (_, s) => s.source === "pattern" ? <Tooltip title="A format check, not a model probability"><Tag>{humanize(s.validation ?? "syntax match")}</Tag></Tooltip> : pct(s.score) },
      { title: "Text position", width: 110, render: (_, s) => <span className="muted small">{s.start}–{s.end}</span> },
    ]} onRow={(s) => ({ onClick: () => show(s.text, [s.text]), className: "result-clickable" })} /> }} />
    <p className="muted small">Select a mention to see it in context. Expand a type for individual occurrences and confidence.</p>
  </div>;
}

function ResolvedCellInner({ value, modules }: { value: unknown; modules: ModuleInfo[] }) {
  const ents = (value as { id: string; name: string; label: string }[] | null) ?? [];
  return <TagRow items={ents.map((e) => ({ key: e.id, text: e.name, label: e.label, hint: `${e.label} · ${e.id}` }))} modules={modules} max={4} />;
}

function ResolvedDetailInner({ value, modules, onFilter }: { value: unknown; modules: ModuleInfo[]; onFilter?: (value: string) => void }) {
  const r = value as ResolvedResult | null;
  const [search, setSearch] = useState("");
  if (!r?.entities.length) return <ResultEmpty description="No entities to resolve in this document." />;
  const entities = r.entities.filter((e) => `${e.canonical ?? e.name} ${e.label} ${e.mentions.join(" ")}`.toLocaleLowerCase().includes(search.toLocaleLowerCase().trim()));
  return <div className="result-section"><ResultSearch value={search} onChange={setSearch} placeholder="Search resolved entities" count={entities.length} unit="entities" />
    <Table className="result-table" size="small" rowKey="id" dataSource={entities} pagination={entities.length > 10 ? { pageSize: 10, showSizeChanger: false } : false} scroll={{ x: 560 }} columns={[
      { title: "Entity", render: (_, e) => <EvidenceButton title={e.canonical ?? e.name} values={e.mentions}><strong>{e.canonical ?? e.name}</strong></EvidenceButton> },
      { title: "Type", width: 110, render: (_, e) => <Tag color={entityColor(e.label, modules)}>{humanize(e.label)}</Tag> },
      { title: "Also mentioned as", render: (_, e) => <span className="muted">{e.mentions.filter((m) => m !== (e.canonical ?? e.name)).join(", ") || "—"}</span> },
      { title: "Mentions", width: 80, align: "right", render: (_, e) => e.spans.length },
      ...(onFilter ? [{ title: "", width: 40, key: "filter", render: (_: unknown, e: ResolvedResult["entities"][number]) => <Tooltip title="Find documents mentioning this entity"><Button size="small" type="text" icon={<FilterOutlined />} aria-label={`Find documents mentioning ${e.canonical ?? e.name}`} onClick={() => onFilter(e.id)} /></Tooltip> }] : []),
    ]} />
    <p className="muted small">Name variants grouped into one entity. Select its name to highlight all mentions.</p>
  </div>;
}

export const EntitiesCell = memo(EntitiesCellInner);
export const ResolvedCell = memo(ResolvedCellInner);
export const EntitiesDetail = memo(EntitiesDetailInner);
export const ResolvedDetail = memo(ResolvedDetailInner);
