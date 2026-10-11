import { Space, Tag, Tooltip, Typography } from "antd";

import type { EntitiesResult, ModuleInfo, ResolvedResult } from "../../api/types";
import { entityColor } from "../../lib/labels";

function TagRow({ items, modules, max }: {
  items: { key: string; text: string; label: string; hint?: string }[]; modules: ModuleInfo[]; max?: number;
}) {
  if (!items.length) return <span className="muted">none</span>;
  const shown = max ? items.slice(0, max) : items;
  return (
    <Space size={[4, 4]} wrap>
      {shown.map((e) => (
        <Tooltip key={e.key} title={e.hint ?? e.label} mouseEnterDelay={0.3}>
          <Tag variant="outlined" color={entityColor(e.label, modules)} style={{ marginInlineEnd: 0 }}>{e.text}</Tag>
        </Tooltip>
      ))}
      {max && items.length > max && <span className="muted">+{items.length - max}</span>}
    </Space>
  );
}

/** NER preview is `{label: [surface…]}`. */
export function EntitiesCell({ value, modules }: { value: unknown; modules: ModuleInfo[] }) {
  const groups = (value as Record<string, string[]> | null) ?? {};
  const items = Object.entries(groups).flatMap(([label, vs]) => vs.map((v) => ({ key: `${label}:${v}`, text: v, label })));
  return <TagRow items={items} modules={modules} max={4} />;
}

export function EntitiesDetail({ value, modules }: { value: unknown; modules: ModuleInfo[] }) {
  const r = value as EntitiesResult | null;
  const groups = Object.entries(r?.groups ?? {});
  if (!groups.length) return <span className="muted">No entities found.</span>;
  return (
    <div className="kv-list">
      {groups.map(([label, values]) => (
        <div key={label} className="kv-row">
          <span className="kv-key"><span className="dot" style={{ background: entityColor(label, modules) }} />{label}</span>
          <TagRow items={values.map((v) => ({ key: v, text: v, label }))} modules={modules} />
        </div>
      ))}
    </div>
  );
}

/** Resolved preview is `[{id, name, label}]`. */
export function ResolvedCell({ value, modules }: { value: unknown; modules: ModuleInfo[] }) {
  const ents = (value as { id: string; name: string; label: string }[] | null) ?? [];
  return <TagRow items={ents.map((e) => ({ key: e.id, text: e.name, label: e.label, hint: `${e.label} · ${e.id}` }))}
                 modules={modules} max={4} />;
}

export function ResolvedDetail({ value, modules, onFilter }: {
  value: unknown; modules: ModuleInfo[]; onFilter?: (value: string) => void;
}) {
  const r = value as ResolvedResult | null;
  if (!r?.entities.length) return <span className="muted">No entities to resolve.</span>;
  return (
    <div className="entity-list">
      {r.entities.map((e) => (
        <div key={e.id} className="entity-row">
          <span className="dot" style={{ background: entityColor(e.label, modules) }} />
          <div className="entity-main">
            <div>
              <Typography.Text strong>{e.canonical ?? e.name}</Typography.Text>
              <Typography.Text type="secondary"> · {e.label}</Typography.Text>
            </div>
            {e.mentions.length > 1 || (e.canonical && e.canonical !== e.mentions[0]) ? (
              <div className="muted small">as {e.mentions.map((m) => `“${m}”`).join(", ")}</div>
            ) : null}
          </div>
          {onFilter ? (
            <Tooltip title="Show every row that mentions this entity">
              <button type="button" className="link-btn mono small" onClick={() => onFilter(e.id)}>{e.id}</button>
            </Tooltip>
          ) : <span className="mono small muted">{e.id}</span>}
        </div>
      ))}
    </div>
  );
}
