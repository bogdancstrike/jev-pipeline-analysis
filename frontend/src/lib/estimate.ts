import type { ModuleInfo, RunRecord } from "../api/types";

/** Prefer complete, successful runs with exactly the same tasks and configuration. */
export function runEstimate(selected: string[], modules: ModuleInfo[], runs: RunRecord[]) {
  const names = [...new Set(selected)].sort();
  const matching = runs.filter((run) => run.status === "done" && run.total >= 20 && (run.wall_s ?? 0) > 0 &&
    run.metrics.failed_rows === 0 && [...run.modules].sort().join(",") === names.join(",") &&
    names.every((name) => {
      const key = modules.find((m) => m.name === name)?.timing_key;
      return !!key && run.metrics.modules[name]?.timing_key === key;
    })).sort((a, b) => b.created_at - a.created_at).slice(0, 5);
  if (matching.length) return {
    perArticle: matching.reduce((sum, run) => sum + run.wall_s!, 0) / matching.reduce((sum, run) => sum + run.total, 0),
    unknown: [] as string[], source: "history" as const, samples: matching.length,
  };
  return { ...secondsPerArticle(selected, modules), source: "benchmarks" as const, samples: 0 };
}

/**
 * Rough run time from single-task benchmarks (profile.rows_per_s, measured alone on the GPU).
 *
 * Model: every GPU task, alone, keeps the GPU ~85-95% busy, so running several mostly adds
 * their costs: seconds/article = sum of 1 / rows_per_s over the selected tasks. Local
 * date parsing is included too. CPU/GPU overlap makes this a conservative approximation.
 */
export function secondsPerArticle(selected: string[], modules: ModuleInfo[]): { perArticle: number; unknown: string[] } {
  let perArticle = 0;
  const unknown: string[] = [];
  for (const name of selected) {
    const m = modules.find((x) => x.name === name);
    if (!m) { unknown.push(name); continue; }
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
