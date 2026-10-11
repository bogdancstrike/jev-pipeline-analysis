import { describe, expect, it } from "vitest";
import { evidenceRanges } from "./EvidenceView";

describe("source evidence selection", () => {
  it("highlights repeated whole names without matching inside different names", () => {
    expect(evidenceRanges("Ann met Annabel. Ann left.", ["Ann"])).toEqual([[0, 3], [17, 20]]);
  });
  it("merges sentence and entity overlaps into one intact passage", () => {
    expect(evidenceRanges("NATO met Maria. More text.", ["NATO", "NATO met Maria.", "Maria"])).toEqual([[0, 15]]);
  });
  it("accepts changed case but never invents a passage for an inferred value", () => {
    expect(evidenceRanges("Bucharest and hxxps://example[.]org", ["BUCHAREST", "https://example.org"])).toEqual([[0, 9]]);
    expect(evidenceRanges("", ["", "inferred"])).toEqual([]);
  });
});
