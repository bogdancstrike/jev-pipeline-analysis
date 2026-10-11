import { memo, useMemo, useState } from "react";

import type { ModuleInfo, Relation } from "../../api/types";
import { humanize } from "../../lib/format";
import { entityColor } from "../../lib/labels";
import { useEvidence } from "./EvidenceView";

interface Node { id: string; name: string; label: string; x: number; y: number; deg: number }

/** Order nodes so connected ones sit next to each other on the circle: short edges, few crossings. */
function connectedOrder(ids: string[], edges: [string, string][]): string[] {
  const adj = new Map(ids.map((i) => [i, new Set<string>()]));
  for (const [a, b] of edges) { adj.get(a)?.add(b); adj.get(b)?.add(a); }
  const seen = new Set<string>();
  const out: string[] = [];
  const byDegree = [...ids].sort((a, b) => (adj.get(b)!.size - adj.get(a)!.size));
  for (const start of byDegree) {
    if (seen.has(start)) continue;
    const queue = [start];
    seen.add(start);
    while (queue.length) {
      const n = queue.shift()!;
      out.push(n);
      for (const m of [...adj.get(n)!].sort((a, b) => adj.get(b)!.size - adj.get(a)!.size)) {
        if (!seen.has(m)) { seen.add(m); queue.push(m); }
      }
    }
  }
  return out;
}

/**
 * Who relates to whom in one row. Entities on a circle ordered by connection, curved directed
 * edges. Edge labels show for small graphs; otherwise hover an entity (or an edge) to read its
 * relations, so labels never pile on top of each other. Colour = entity type (legend below).
 */
function RelationGraphInner({ relations, modules }: { relations: Relation[]; modules: ModuleInfo[] }) {
  const showEvidence = useEvidence();
  const [focusNode, setFocusNode] = useState<string | null>(null);
  const [focusEdge, setFocusEdge] = useState<number | null>(null);
  const { nodes, edges, W, H, cx, cy } = useMemo(() => {
    const info = new Map<string, { name: string; label: string }>();
    const pairs: [string, string][] = [];
    for (const r of relations) {
      const a = r.head_id ?? `t:${r.head}`, b = r.tail_id ?? `t:${r.tail}`;
      info.set(a, { name: r.head, label: r.head_label ?? "other" });
      info.set(b, { name: r.tail, label: r.tail_label ?? "other" });
      pairs.push([a, b]);
    }
    const order = connectedOrder([...info.keys()], pairs);
    const W = 640, H = Math.max(260, Math.min(460, 140 + order.length * 22));
    const cx = W / 2, cy = H / 2, rx = W / 2 - 150, ry = H / 2 - 34;
    const deg = new Map<string, number>();
    for (const [a, b] of pairs) { deg.set(a, (deg.get(a) ?? 0) + 1); deg.set(b, (deg.get(b) ?? 0) + 1); }
    const nodes: Node[] = order.map((id, i) => {
      const t = (i / order.length) * Math.PI * 2 - Math.PI / 2;
      return { id, ...info.get(id)!, x: cx + rx * Math.cos(t), y: cy + ry * Math.sin(t), deg: deg.get(id) ?? 1 };
    });
    const at = new Map(nodes.map((n) => [n.id, n]));
    const edges = relations.map((r, i) => ({ i, r, a: at.get(pairs[i][0])!, b: at.get(pairs[i][1])! }));
    return { nodes, edges, W, H, cx, cy };
  }, [relations]);

  if (!relations.length) return null;
  const types = [...new Set(nodes.map((n) => n.label))];
  const showAllLabels = relations.length <= 4;
  const active = (e: { i: number; a: Node; b: Node }) =>
    focusEdge === e.i || (focusNode !== null && (e.a.id === focusNode || e.b.id === focusNode));
  const anyFocus = focusNode !== null || focusEdge !== null;

  return (
    <figure className="relgraph">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${relations.length} relations between ${nodes.length} entities`}>
        <defs>
          <marker id="rg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="context-stroke" />
          </marker>
        </defs>
        {edges.map((e) => {
          const { a, b } = e;
          if (!a || !b) return null;
          // Quadratic curve bowing towards the centre: parallel edges separate, arrows stay readable.
          const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
          const qx = mx + (cx - mx) * 0.35, qy = my + (cy - my) * 0.35;
          const pad = 9;
          const sa = Math.hypot(qx - a.x, qy - a.y) || 1, sb = Math.hypot(qx - b.x, qy - b.y) || 1;
          const x1 = a.x + ((qx - a.x) / sa) * pad, y1 = a.y + ((qy - a.y) / sa) * pad;
          const x2 = b.x + ((qx - b.x) / sb) * pad, y2 = b.y + ((qy - b.y) / sb) * pad;
          const on = active(e);
          const lx = 0.25 * x1 + 0.5 * qx + 0.25 * x2, ly = 0.25 * y1 + 0.5 * qy + 0.25 * y2;
          const d = `M${x1},${y1} Q${qx},${qy} ${x2},${y2}`;
          return (
            <g key={e.i} className={`rg-edge${on ? " is-on" : ""}${anyFocus && !on ? " is-dim" : ""}`}
               tabIndex={0} role="button" aria-label={`Highlight ${e.r.head} ${humanize(e.r.relation)} ${e.r.tail}`}
               onClick={() => showEvidence(`${e.r.head} → ${e.r.tail}`, [e.r.evidence ?? "", e.r.head, e.r.tail])}
               onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); showEvidence(`${e.r.head} → ${e.r.tail}`, [e.r.evidence ?? "", e.r.head, e.r.tail]); } }}
               onFocus={() => setFocusEdge(e.i)} onBlur={() => setFocusEdge(null)}
               onMouseEnter={() => setFocusEdge(e.i)} onMouseLeave={() => setFocusEdge(null)}>
              <path d={d} className="rg-edge-hit" />
              <path d={d} className="rg-edge-line" markerEnd="url(#rg-arrow)" />
              {(showAllLabels || on) && (
                <text x={lx} y={ly} textAnchor="middle" dy="0.32em" className="rg-edge-label">
                  {humanize(e.r.relation)} · {Math.round(e.r.confidence * 100)}%
                </text>
              )}
            </g>
          );
        })}
        {nodes.map((n) => {
          const right = n.x >= cx + 1;
          const centre = Math.abs(n.x - cx) < 1;
          const dim = anyFocus && focusNode !== n.id &&
            !edges.some((e) => active(e) && (e.a.id === n.id || e.b.id === n.id));
          return (
            <g key={n.id} className={`rg-node${dim ? " is-dim" : ""}`} tabIndex={0} role="button" aria-label={`Highlight ${n.name}`}
               onClick={() => showEvidence(n.name, [n.name])}
               onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); showEvidence(n.name, [n.name]); } }}
               onMouseEnter={() => setFocusNode(n.id)} onMouseLeave={() => setFocusNode(null)}
               onFocus={() => setFocusNode(n.id)} onBlur={() => setFocusNode(null)}>
              <circle cx={n.x} cy={n.y} r={16} fill="transparent" />
              <circle cx={n.x} cy={n.y} r={Math.min(9, 5 + n.deg)} fill={entityColor(n.label, modules)} stroke="var(--bg)" strokeWidth={2} />
              <text x={centre ? n.x : n.x + (right ? 14 : -14)} y={centre ? n.y - 16 : n.y} dy={centre ? 0 : "0.32em"}
                    textAnchor={centre ? "middle" : right ? "start" : "end"} className="rg-node-label">
                {n.name.length > 26 ? `${n.name.slice(0, 25)}…` : n.name}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="relgraph-foot">
        <span className="legend">
          {types.map((l) => <span key={l} className="legend-item"><span className="swatch swatch-round" style={{ background: entityColor(l, modules) }} />{l}</span>)}
        </span>
        {!showAllLabels && <span className="muted small">Hover an entity or an arrow to read its relations.</span>}
      </figcaption>
    </figure>
  );
}

export const RelationGraph = memo(RelationGraphInner);
