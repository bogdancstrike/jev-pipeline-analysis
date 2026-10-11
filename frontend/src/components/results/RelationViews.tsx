import { memo } from "react";
import { ArrowRightOutlined } from "@ant-design/icons";
import { Tooltip, Typography } from "antd";

import type { ClusterResult, ModuleInfo, Relation } from "../../api/types";
import { RelationGraph } from "./RelationGraph";
import { humanize, pct } from "../../lib/format";

function Triple({ r }: { r: Pick<Relation, "head" | "relation" | "tail"> }) {
  return (
    <span className="triple">
      <span className="triple-ent">{r.head}</span>
      <span className="triple-rel">{humanize(r.relation)} <ArrowRightOutlined /></span>
      <span className="triple-ent">{r.tail}</span>
    </span>
  );
}

function RelationsCellInner({ value }: { value: unknown }) {
  const rels = (value as Relation[] | null) ?? [];
  if (!rels.length) return <span className="muted">–</span>;
  return (
    <Tooltip title={<div>{rels.map((r, i) => <div key={i}>{r.head} · {humanize(r.relation)} · {r.tail}</div>)}</div>}>
      <span className="cell-ellipsis"><Triple r={rels[0]} />{rels.length > 1 && <span className="muted"> +{rels.length - 1}</span>}</span>
    </Tooltip>
  );
}

function RelationsDetailInner({ value, modules }: { value: unknown; modules: ModuleInfo[] }) {
  const rels = ((value as { relations?: Relation[] } | null)?.relations) ?? [];
  if (!rels.length) return <span className="muted">No relation stated between the entities in this text.</span>;
  return (
    <div className="relation-list">
      <RelationGraph relations={rels} modules={modules} />
      {rels.map((r, i) => (
        <div key={i} className="relation-row">
          <Triple r={r} />
          <span className="muted small">{pct(r.confidence)}</span>
          {r.evidence && <Typography.Paragraph type="secondary" className="evidence" ellipsis={{ rows: 2, expandable: true }}>
            “{r.evidence}”
          </Typography.Paragraph>}
        </div>
      ))}
    </div>
  );
}

function ClusterCellInner({ value }: { value: unknown }) {
  const c = value as ClusterResult | null;
  if (!c) return <span className="muted">–</span>;
  return <Tooltip title={`Reported in ${c.size} rows`}><span className="pill mono">{c.cluster} · {c.size}</span></Tooltip>;
}

function ClusterDetailInner({ value, onOpenRow }: { value: unknown; onOpenRow?: (idx: number) => void }) {
  const c = value as ClusterResult | null;
  if (!c) return <span className="muted">No other row reports this event.</span>;
  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <span className="pill mono">{c.cluster}</span>{" "}
        <Typography.Text type="secondary">Same event reported in {c.size} rows. Also in:</Typography.Text>
      </div>
      <div className="peer-list">
        {(c.peers ?? []).map((p, i) => (
          <button key={p} type="button" className="peer" onClick={() => onOpenRow?.(p)}>Row {c.peer_ids?.[i] ?? p + 1}</button>
        ))}
      </div>
    </div>
  );
}

export const RelationsCell = memo(RelationsCellInner);

export const ClusterCell = memo(ClusterCellInner);

export const RelationsDetail = memo(RelationsDetailInner);

export const ClusterDetail = memo(ClusterDetailInner);
