import type { ModuleInfo } from "../api/types";

/** Turning a module on turns on everything it requires (transitively). */
export function withRequirements(selected: string[], name: string, modules: ModuleInfo[]): string[] {
  const by = new Map(modules.map((m) => [m.name, m]));
  const out = new Set(selected);
  const stack = [name];
  while (stack.length) {
    const n = stack.pop()!;
    if (out.has(n) && n !== name) continue;
    out.add(n);
    stack.push(...(by.get(n)?.requires ?? []));
  }
  return modules.map((m) => m.name).filter((n) => out.has(n));
}

/** Turning a module off turns off everything that requires it (transitively). */
export function withoutDependents(selected: string[], name: string, modules: ModuleInfo[]): string[] {
  const drop = new Set([name]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const m of modules) {
      if (!drop.has(m.name) && m.requires.some((r) => drop.has(r))) {
        drop.add(m.name);
        grew = true;
      }
    }
  }
  return selected.filter((n) => !drop.has(n));
}

/** Names of selected modules that need `name`: why it cannot be switched off alone. */
export function requiredBy(selected: string[], name: string, modules: ModuleInfo[]): string[] {
  return modules.filter((m) => selected.includes(m.name) && m.requires.includes(name)).map((m) => m.title);
}

/** Presentation groups for the picker. Unknown modules land in "More", so new ones still show. */
export const GROUPS: { title: string; modules: string[] }[] = [
  { title: "Classification & routing", modules: ["language", "category", "iptc", "genre", "relevance", "routing"] },
  { title: "Entities & indicators", modules: ["ner", "entity_resolution", "relations", "ioc", "fields"] },
  { title: "Events & dates", modules: ["event", "event_coreference", "temporal"] },
  { title: "Tone & risk", modules: ["sentiment", "emotion", "intent", "risk", "toxicity", "propaganda", "extremism"] },
];

export function groupModules(modules: ModuleInfo[]): { title: string; items: ModuleInfo[] }[] {
  const known = new Set(GROUPS.flatMap((g) => g.modules));
  const groups = GROUPS.map((g) => ({ title: g.title, items: modules.filter((m) => g.modules.includes(m.name)) }));
  const rest = modules.filter((m) => !known.has(m.name));
  if (rest.length) groups.push({ title: "More", items: rest });
  return groups.filter((g) => g.items.length);
}
