import type { ModuleInfo } from "../api/types";
import { humanize } from "./format";
import { CATEGORICAL } from "../theme/tokens";

/** Stable colour per label: its position in the module's configured label list. */
export function labelColor(label: string, order: string[]): string {
  const i = order.indexOf(label);
  return CATEGORICAL[(i < 0 ? hash(label) : i) % CATEGORICAL.length];
}

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

export type Tone = "danger" | "warning" | "success" | "neutral";

/**
 * Where a label *means* something, it gets a semantic tone instead of a categorical hue:
 * harm is red, approval green. Everything else stays neutral, so red keeps its meaning.
 */
export function labelTone(module: string, label: string): Tone | null {
  switch (module) {
    case "sentiment":
      return label === "negative" ? "danger" : label === "positive" ? "success" : "neutral";
    case "toxicity":
      return label === "non_toxic" ? "neutral" : "danger";
    case "propaganda":
      return label === "none" ? "neutral" : "warning";
    case "intent":
      return ["incite", "threaten", "scam", "recruit"].includes(label) ? "danger" : null;
    case "event":
      return label === "no_event" ? "neutral" : null;
    default:
      return null;
  }
}

export const labelOrder = (m?: ModuleInfo) => Object.keys(m?.labels ?? {});

/** Entity-type colours come from the NER module's label order. */
export const entityColor = (label: string, modules: ModuleInfo[]) =>
  labelColor(label, labelOrder(modules.find((m) => m.name === "ner")));

/**
 * How a label reads. Keys are snake_case for machines; people get words. Language codes
 * are the exception: "RO" in a dense cell, the configured name ("Romanian") elsewhere.
 */
export function labelText(module: ModuleInfo, key: string, compact = false): string {
  if (module.name === "language") return compact ? key.toUpperCase() : (module.labels?.[key] || key.toUpperCase());
  return module.label_names?.[key] ?? humanize(key);
}
