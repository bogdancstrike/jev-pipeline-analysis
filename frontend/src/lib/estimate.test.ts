import { describe, expect, it } from "vitest";
import type { ModuleInfo, ModuleMetrics, RunRecord } from "../api/types";
import { runEstimate } from "./estimate";

const modules = [{ name: "category", title: "Topic", engine: "laya", timing_key: "current", profile: { rows_per_s: 50 } }] as ModuleInfo[];
const metrics = (key: string): ModuleMetrics => ({ timing_key: key, rows: 100, batches: 7,
  start_s: 0, end_s: 4, wall_s: 4, busy_s: 4, parallelism: 1, rows_per_s: 25,
  batch_ms: { p50: null, p95: null, p99: null, mean: null },
  row_ms: { p50: null, p95: null, p99: null, mean: null }, engine: "laya", errors: 0 });
const run = (changes: Partial<RunRecord> = {}): RunRecord => ({
  id: "one", filename: "sample", status: "done", total: 100, modules: ["category"], created_at: 1,
  wall_s: 4, rows_per_s: 25, metrics: { failed_rows: 0, peak_rows_per_s: 25,
    modules: { category: metrics("current") } }, ...changes,
});
describe("runtime estimates", () => {
  it("learns from matching completed runs and weights by record count", () => {
    const estimate = runEstimate(["category"], modules, [run(), run({ total: 300, wall_s: 8 })]);
    expect(estimate.source).toBe("history");
    expect(estimate.perArticle).toBe(12 / 400);
    expect(estimate.samples).toBe(2);
  });
  it("rejects old settings, different tasks, failures and tiny runs", () => {
    const bad = [run({ total: 1 }), run({ modules: ["category", "ner"] }), run({ status: "cancelled" }),
      run({ metrics: { failed_rows: 1, peak_rows_per_s: 0, modules: {} } }),
      run({ metrics: { failed_rows: 0, peak_rows_per_s: 0, modules: { category: metrics("old") } } })];
    expect(runEstimate(["category"], modules, bad)).toMatchObject({ source: "benchmarks", perArticle: 1 / 50 });
  });
  it("includes measured CPU parsing costs and does not invent a rate for unmeasured tasks", () => {
    const temporal = { name: "temporal", title: "Temporal normalization", engine: null, profile: { rows_per_s: 20 } } as ModuleInfo;
    expect(runEstimate(["category", "temporal"], [...modules, temporal], []).perArticle).toBeCloseTo(0.07);
    expect(runEstimate(["temporal"], [{ ...temporal, profile: {} }], []).unknown).toEqual(["Temporal normalization"]);
  });
  it("updates after deletion and reports missing configuration benchmarks", () => {
    expect(runEstimate(["category"], modules, [run()]).source).toBe("history");
    expect(runEstimate(["category"], modules, []).source).toBe("benchmarks");
    expect(runEstimate(["category"], [{ ...modules[0], profile: {} }], []).unknown).toEqual(["Topic"]);
  });
});
