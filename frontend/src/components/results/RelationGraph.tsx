import { useMemo, useState } from "react";

import type { ModuleInfo, Relation } from "../../api/types";
import { humanize } from "../../lib/format";
import { entityColor } from "../../lib/labels";

interface Node { id: string; name: string; label: string; x: number; y: number }

/**
 * Who relates to whom in one row: entities on a circle (stable, never overlapping for a
 * handful of nodes), directed edges labelled with the relation. Hover an entity to isolate
 * its relations. Node colour = entity type, with the legend below so colour is not the only key.
 */
export function RelationGraph({ relations, modules }: { relations: Relation[]; modules: ModuleInfo[] }) {
  const [focus, setFocus] = useState<string | null>(null);
  const { nodes, edges, W, H } = useMemo(() => {
    const byId = new Map<string, { name: string; label: string }>();
    for (const r of relations) {
      byId.set(r.head_id ?? r.head, { name: r.head, label: r.head_label ?? "entity" });
      byId.set(r.tail_id ?? r.tail, { name: r.tail, label: r.tail_label ?? "entity" });
    }
    const W = 560, H = Math.max(240, Math.min(420, 120 + byId.size * 24));
    const cx = W / 2, cy = H / 2, rx = W / 2 - 110, ry = H / 2 - 36;
    const nodes: Node[] = [...byId.entries()].map(([id, v], i, all) => {
      const a = (i / all.length) * Math.PI * 2 - Math.PI / 2;
      return { id, ...v, x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a) };
    });
    const at = new Map(nodes.map((n) => [n.id, n]));
    const edges = relations.map((r, i) => ({ key: i, r, a: at.get(r.head_id ?? r.head)!, b: at.get(r.tail_id ?? r.tail)! }));
    return { nodes, edges, W, H };
  }, [relations]);

  if (!relations.length) return null;
  const labels = [...new Set(nodes.map((n) => n.label))];
  const dim = (ids: string[]) => focus !== null && !ids.includes(focus);

  return (
    <figure className="relgraph" aria-label="Relation graph">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${relations.length} relations between ${nodes.length} entities`}>
        <defs>
          <marker id="rg-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--text-3)" />
          </marker>
        </defs>
        {edges.map(({ key, r, a, b }) => {
          if (!a || !b) return null;
          const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
          const pad = 14;
          const x1 = a.x + (dx / len) * pad, y1 = a.y + (dy / len) * pad, x2 = b.x - (dx / len) * pad, y2 = b.y - (dy / len) * pad;
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
          return (
            <g key={key} opacity={dim([a.id, b.id]) ? 0.12 : 1}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--text-3)" strokeWidth={1.5} markerEnd="url(#rg-arrow)" />
              <text x={mx} y={my} dy="-0.4em" textAnchor="middle" className="rg-edge-label">
                {humanize(r.relation)} · {Math.round(r.confidence * 100)}%
              </text>
            </g>
          );
        })}
        {nodes.map((n) => {
          const right = n.x >= W / 2;
          return (
            <g key={n.id} opacity={dim([n.id]) ? 0.25 : 1} onMouseEnter={() => setFocus(n.id)} onMouseLeave={() => setFocus(null)}
               onFocus={() => setFocus(n.id)} onBlur={() => setFocus(null)} tabIndex={0} className="rg-node">
              <circle cx={n.x} cy={n.y} r={14} fill="transparent" />
              <circle cx={n.x} cy={n.y} r={7} fill={entityColor(n.label, modules)} stroke="var(--surface)" strokeWidth={2} />
              <text x={n.x + (right ? 12 : -12)} y={n.y} dy="0.32em" textAnchor={right ? "start" : "end"} className="rg-node-label">
                {n.name.length > 28 ? `${n.name.slice(0, 27)}…` : n.name}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="legend">
        {labels.map((l) => <span key={l} className="legend-item"><span className="swatch swatch-round" style={{ background: entityColor(l, modules) }} />{l}</span>)}
      </figcaption>
    </figure>
  );
}
