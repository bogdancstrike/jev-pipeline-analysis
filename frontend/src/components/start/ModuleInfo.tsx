import { Tag, Typography } from "antd";

import type { AppConfig, ModuleInfo as Info } from "../../api/types";
import { labelText } from "../../lib/labels";

const SPEED: Record<string, { text: string; color: string }> = {
  fast: { text: "Fast", color: "success" },
  medium: { text: "Medium", color: "processing" },
  slow: { text: "Slow", color: "warning" },
};

/** Everything a user needs before switching a task on: what it outputs, how fast, what it costs others. */
export function pipelineImpact(m: Info, config: AppConfig, selected: string[]): string[] {
  const title = (n: string) => config.modules.find((x) => x.name === n)?.title ?? n;
  const out: string[] = [];
  if (!m.engine) {
    out.push("Runs on the CPU inside the backend: no GPU, no queueing behind other tasks.");
  } else {
    const peers = (m.shares_engine_with ?? []).filter((n) => selected.includes(n));
    out.push(peers.length
      ? `Shares the ${m.engine} engine with ${peers.length} other selected task${peers.length > 1 ? "s" : ""} (${peers.map(title).join(", ")}). They queue for the same model on the GPU, so each one added slows the others.`
      : `Runs on the ${m.engine} engine; no other selected task uses it, so it overlaps with them.`);
  }
  if (m.requires.length) out.push(`Needs ${m.requires.map(title).join(" and ")}: selecting it adds ${m.requires.length > 1 ? "them" : "it"}, and it can only start on a row once ${m.requires.length > 1 ? "they have" : "it has"} finished that row.`);
  if (m.dependents?.length) out.push(`${m.dependents.map(title).join(", ")} need${m.dependents.length === 1 ? "s" : ""} this: turning it off turns ${m.dependents.length === 1 ? "it" : "them"} off.`);
  if (m.scope === "job") out.push("Runs once at the end, comparing rows with each other, after its inputs cover every row: it adds to the total time instead of overlapping.");
  if (m.kind === "relations" && m.engine_kind === "systemone") out.push("Asks one question per entity pair (up to 6 per row): the most expensive LLM path.");
  return out;
}

export function ModuleInfoContent({ m, config, selected }: { m: Info; config: AppConfig; selected: string[] }) {
  const options = m.labels ? Object.entries(m.labels) : [];
  const engine = m.engine ? config.engines?.[m.engine] : undefined;
  const speed = SPEED[m.profile?.speed ?? ""];
  return (
    <div className="module-info">
      <div className="module-info-head">
        <b>{m.title}</b>
        {speed && <Tag color={speed.color} variant="filled">{speed.text}</Tag>}
      </div>
      <p>{m.description}</p>

      {options.length > 0 && (
        <>
          <div className="mi-title">{m.kind === "label" ? "Chooses one of" : m.kind === "entities" ? "Finds" : "Types"} ({options.length})</div>
          <ul className="mi-options">
            {options.slice(0, 14).map(([k, d]) => (
              <li key={k}><span className="mi-key">{labelText(m, k)}</span>{d && <span className="muted"> · {d}</span>}</li>
            ))}
            {options.length > 14 && <li className="muted">+{options.length - 14} more (Admin page)</li>}
          </ul>
        </>
      )}
      {m.records && (
        <>
          <div className="mi-title">Extracts</div>
          {Object.entries(m.records).map(([rec, fields]) => <div key={rec}><span className="mi-key">{rec}</span>: {fields.join(", ")}</div>)}
        </>
      )}

      <div className="mi-title">Model</div>
      <div>{m.engine ? <>{m.engine}{engine?.description ? <span className="muted"> · {engine.description}</span> : null}</> : "Local CPU logic (no model)"}</div>

      <div className="mi-title">Speed</div>
      <div>{m.profile?.throughput ?? "Not benchmarked yet."}</div>
      {m.profile?.notes && <Typography.Text type="secondary" className="small">{m.profile.notes}</Typography.Text>}

      <div className="mi-title">Effect on the pipeline</div>
      <ul className="mi-impact">{pipelineImpact(m, config, selected).map((t) => <li key={t}>{t}</li>)}</ul>
    </div>
  );
}
