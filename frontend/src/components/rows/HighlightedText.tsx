import { Fragment } from "react";

import type { ModuleInfo, ResolvedEntity, Span } from "../../api/types";
import { segments } from "../../lib/highlight";
import { entityColor } from "../../lib/labels";

/** The text with entities marked inline: the fastest way to judge whether NER is right. */
export function HighlightedText({ text, spans, resolved, modules }: {
  text: string; spans: Span[]; resolved: ResolvedEntity[]; modules: ModuleInfo[];
}) {
  // Which resolved entity a span belongs to, by exact offsets.
  const owner = new Map<string, ResolvedEntity>();
  for (const e of resolved) for (const [s, end] of e.spans) owner.set(`${s}:${end}`, e);

  if (!text) return <div className="doc muted">(empty text)</div>;
  return (
    <div className="doc">
      {segments(text, spans).map((seg, i) => {
        if (!seg.span) return <Fragment key={i}>{seg.text}</Fragment>;
        const c = entityColor(seg.span.label, modules);
        const ent = owner.get(`${seg.span.start}:${seg.span.end}`);
        const title = `${seg.span.label} · ${Math.round(seg.span.score * 100)}%${ent ? ` · ${ent.canonical ?? ent.name} (${ent.id})` : ""}`;
        return (
          <mark key={i} className="ent" style={{ background: `color-mix(in srgb, ${c} 14%, transparent)`, borderColor: c }} title={title}>
            {seg.text}<span className="ent-label" style={{ color: c }}>{seg.span.label}</span>
          </mark>
        );
      })}
    </div>
  );
}
