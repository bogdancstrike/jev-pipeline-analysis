import { describe, expect, it } from "vitest";

import { segments } from "./highlight";

describe("segments", () => {
  it("splits text into plain and marked parts that rebuild the original", () => {
    const text = "NATO met in Brussels.";
    const out = segments(text, [{ start: 12, end: 20 }, { start: 0, end: 4 }]);
    expect(out.map((s) => s.text).join("")).toBe(text);
    expect(out.filter((s) => s.span).map((s) => s.text)).toEqual(["NATO", "Brussels"]);
  });
  it("drops overlapping and out-of-range spans instead of corrupting the text", () => {
    const out = segments("abcdef", [{ start: 0, end: 3 }, { start: 2, end: 5 }, { start: 4, end: 99 }]);
    expect(out.map((s) => s.text).join("")).toBe("abcdef");
    expect(out.filter((s) => s.span)).toHaveLength(1);
  });
});
