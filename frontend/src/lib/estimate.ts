import type { ModuleInfo } from "../api/types";

/**
 * Rough run time from single-task benchmarks (profile.rows_per_s, measured alone on the GPU).
 *
 * Model: every GPU task, alone, keeps the GPU ~85-95% busy, so running several mostly adds
 * their costs: seconds/article = sum of 1 / rows_per_s over the selected GPU tasks. CPU-only
 * tasks are negligible. Validated against a measured all-task run (docs/BENCHMARKS.md).
 */
export function secondsPerArticle(selected: string[], modules: ModuleInfo[]): { perArticle: number; unknown: string[] } {
  let perArticle = 0;
  const unknown: string[] = [];
  for (const name of selected) {
    const m = modules.find((x) => x.name === name);
    if (!m || !m.engine) continue; // local CPU work: thousands of articles/s
    const rps = m.profile?.rows_per_s;
    if (rps && rps > 0) perArticle += 1 / rps;
    else unknown.push(m.title);
  }
  return { perArticle, unknown };
}

export function engineGroups(selected: string[], modules: ModuleInfo[]): { engine: string; tasks: string[] }[] {
  const by = new Map<string, string[]>();
  for (const name of selected) {
    const m = modules.find((x) => x.name === name);
    if (!m) continue;
    const e = m.engine ?? "local CPU";
    by.set(e, [...(by.get(e) ?? []), m.title]);
  }
  return [...by.entries()].map(([engine, tasks]) => ({ engine, tasks })).sort((a, b) => b.tasks.length - a.tasks.length);
}
