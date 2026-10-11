import { CheckOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";

import type { ModuleInfo } from "../../api/types";
import { groupModules, requiredBy, withoutDependents, withRequirements } from "../../lib/modules";

/**
 * Which analyses to run. Dependencies are handled for the user: picking Relations brings
 * in Entities and Resolution; dropping Entities drops what needs it.
 */
export function ModulePicker({ modules, selected, onChange, disabled }: {
  modules: ModuleInfo[]; selected: string[]; onChange: (s: string[]) => void; disabled?: boolean;
}) {
  const toggle = (m: ModuleInfo) => {
    if (selected.includes(m.name)) onChange(withoutDependents(selected, m.name, modules));
    else onChange(withRequirements(selected, m.name, modules));
  };
  const all = modules.map((m) => m.name);

  return (
    <div className="picker">
      <div className="picker-head">
        <span className="section-title">Analyses</span>
        <span className="picker-actions">
          <Button type="link" size="small" disabled={disabled} onClick={() => onChange(all)}>All</Button>
          <Button type="link" size="small" disabled={disabled}
                  onClick={() => onChange(withRequirements([], "category", modules).filter((n) => all.includes(n)))}>
            Topic only
          </Button>
        </span>
      </div>
      {groupModules(modules).map((g) => (
        <div key={g.title} className="picker-group">
          <div className="picker-group-title">{g.title}</div>
          <div className="picker-chips">
            {g.items.map((m) => {
              const on = selected.includes(m.name);
              const needers = on ? requiredBy(selected, m.name, modules) : [];
              const tip = (
                <div>
                  <div>{m.description}</div>
                  {m.requires.length > 0 && <div className="tip-meta">Needs: {m.requires.map((r) => modules.find((x) => x.name === r)?.title ?? r).join(", ")}</div>}
                  {needers.length > 0 && <div className="tip-meta">Used by: {needers.join(", ")}</div>}
                  {m.engine && <div className="tip-meta">Model engine: {m.engine}</div>}
                </div>
              );
              return (
                <Tooltip key={m.name} title={tip} mouseEnterDelay={0.35}>
                  <button type="button" className={`chip${on ? " is-on" : ""}`} aria-pressed={on}
                          disabled={disabled} onClick={() => toggle(m)}>
                    <span className="chip-check" aria-hidden>{on && <CheckOutlined />}</span>
                    {m.title}
                    {m.engine && <ThunderboltOutlined className="chip-llm" aria-label={`runs on ${m.engine}`} />}
                  </button>
                </Tooltip>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
