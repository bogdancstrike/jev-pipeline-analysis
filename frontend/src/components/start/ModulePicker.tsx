import { CheckOutlined, InfoCircleOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Button, Popover, Tooltip } from "antd";
import { memo } from "react";

import type { AppConfig, ModuleInfo } from "../../api/types";
import { groupModules, requiredBy, withoutDependents, withRequirements } from "../../lib/modules";
import { ModuleInfoContent } from "./ModuleInfo";

/** Fast = tasks benchmarked as fast, plus whatever they need to run. */
export function fastPreset(modules: ModuleInfo[]): string[] {
  return modules.filter((m) => m.profile?.speed === "fast")
    .reduce<string[]>((sel, m) => withRequirements(sel, m.name, modules), []);
}

/** Preset buttons: All / Fast / Topic only / None. */
export function Presets({ modules, selected, onChange, disabled }: {
  modules: ModuleInfo[]; selected: string[]; onChange: (s: string[]) => void; disabled?: boolean;
}) {
  const all = modules.map((m) => m.name);
  const fast = fastPreset(modules);
  const topic = withRequirements([], "category", modules).filter((n) => all.includes(n));
  const same = (a: string[]) => a.length === selected.length && a.every((n) => selected.includes(n));
  const presets = [
    { key: "all", label: "All", value: all, hint: "Every task" },
    { key: "fast", label: "Fast", value: fast, hint: fast.length ? `Tasks benchmarked as fast (${fast.length})` : "No task is benchmarked as fast yet" },
    { key: "topic", label: "Topic only", value: topic, hint: "Just the topic classifier" },
    { key: "none", label: "None", value: [] as string[], hint: "Clear the selection" },
  ];
  return (
    <span className="presets" role="group" aria-label="Presets">
      {presets.map((p) => (
        <Tooltip key={p.key} title={p.hint}>
          <Button size="small" type={same(p.value) ? "primary" : "default"} disabled={disabled || (p.key === "fast" && !fast.length)}
                  onClick={() => onChange(p.value)}>{p.label}</Button>
        </Tooltip>
      ))}
    </span>
  );
}

const Chip = memo(function Chip({ m, on, neededBy, disabled, onToggle, info }: {
  m: ModuleInfo; on: boolean; neededBy: string[]; disabled?: boolean; onToggle: (m: ModuleInfo) => void; info: React.ReactNode;
}) {
  return (
    <span className={`chip${on ? " is-on" : ""}${disabled ? " is-disabled" : ""}`}>
      <button type="button" className="chip-main" aria-pressed={on} disabled={disabled} onClick={() => onToggle(m)}
              title={neededBy.length ? `Needed by ${neededBy.join(", ")}` : undefined}>
        <span className="chip-check" aria-hidden>{on && <CheckOutlined />}</span>
        {m.title}
        {m.profile?.speed === "fast" && <ThunderboltOutlined className="chip-fast" aria-label="fast" />}
      </button>
      <Popover content={info} trigger={["hover", "click"]} placement="bottom" mouseEnterDelay={0.25}
               classNames={{ root: "module-info-pop" }} destroyOnHidden>
        <button type="button" className="chip-info" aria-label={`About ${m.title}`}><InfoCircleOutlined /></button>
      </Popover>
    </span>
  );
});

/**
 * Which analyses to run. Dependencies are handled for the user: picking Relations brings
 * in Entities and Resolution; dropping Entities drops what needs it. Every task has an info
 * point: what it outputs, which model, how fast, and what it costs the rest of the pipeline.
 */
export function ModulePicker({ config, selected, onChange, disabled }: {
  config: AppConfig; selected: string[]; onChange: (s: string[]) => void; disabled?: boolean;
}) {
  const modules = config.modules;
  const toggle = (m: ModuleInfo) => {
    if (selected.includes(m.name)) onChange(withoutDependents(selected, m.name, modules));
    else onChange(withRequirements(selected, m.name, modules));
  };
  return (
    <div className="picker">
      {groupModules(modules).map((g) => (
        <div key={g.title} className="picker-group">
          <div className="picker-group-title">{g.title}</div>
          <div className="picker-chips">
            {g.items.map((m) => {
              const on = selected.includes(m.name);
              return (
                <Chip key={m.name} m={m} on={on} disabled={disabled} onToggle={toggle}
                      neededBy={on ? requiredBy(selected, m.name, modules) : []}
                      info={<ModuleInfoContent m={m} config={config} selected={selected} />} />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
