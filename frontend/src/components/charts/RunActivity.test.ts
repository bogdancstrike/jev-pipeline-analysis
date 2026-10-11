import { describe, expect, it } from "vitest";
import type { RunRecord } from "../../api/types";
import { activityDays } from "./RunActivity";

const run = (date: Date, total: number, status: RunRecord["status"] = "done"): RunRecord => ({
  id: String(date.getTime()), filename: "test.csv", status, total, modules: [], created_at: date.getTime() / 1000,
  wall_s: 1, rows_per_s: total, metrics: { modules: {}, peak_rows_per_s: total, failed_rows: 0 },
});

describe("daily run activity", () => {
  const today = new Date(2026, 9, 11, 15);
  it("includes quiet days and groups records at local midnight boundaries", () => {
    const days = activityDays([
      run(new Date(2026, 9, 10, 23, 59), 10), run(new Date(2026, 9, 11), 20), run(new Date(2026, 9, 11, 10), 30),
    ], today);
    expect(days).toHaveLength(7);
    expect(days.slice(0, 5).every((day) => day.records === 0 && day.runs === 0)).toBe(true);
    expect(days[5]).toMatchObject({ records: 10, runs: 1 });
    expect(days[6]).toMatchObject({ records: 50, runs: 2 });
  });
  it("excludes failed, cancelled, future and out-of-window runs", () => {
    const days = activityDays([
      run(new Date(2026, 9, 11), 10, "failed"), run(new Date(2026, 9, 11), 10, "cancelled"),
      run(new Date(2026, 9, 4, 23, 59), 10), run(new Date(2026, 9, 12), 10), run(new Date(2026, 9, 5), 5),
    ], today);
    expect(days.reduce((sum, day) => sum + day.records, 0)).toBe(5);
    expect(days[0]).toMatchObject({ records: 5, runs: 1 });
  });
});
