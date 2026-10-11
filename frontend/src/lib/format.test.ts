import { describe, expect, it } from "vitest";

import { ago, duration, humanize } from "./format";

describe("format", () => {
  it("humanizes snake_case keys", () => {
    expect(humanize("loaded_language")).toBe("Loaded language");
    expect(humanize("government agency")).toBe("Government agency");
  });
  it("formats durations at a readable precision", () => {
    expect(duration(null)).toBe("–");
    expect(duration(0.005)).toBe("0.005 s");
    expect(duration(3.274)).toBe("3.27 s");
    expect(duration(42)).toBe("42.0 s");
    expect(duration(125)).toBe("2 min 5 s");
  });
  it("says relative times in words", () => {
    expect(ago(1000, 1_010_000)).toBe("just now");
    expect(ago(0, 7_200_000)).toBe("2 h ago");
  });
});
