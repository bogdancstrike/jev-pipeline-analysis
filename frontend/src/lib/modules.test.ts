import { describe, expect, it } from "vitest";

import type { ModuleInfo } from "../api/types";
import { groupModules, requiredBy, withoutDependents, withRequirements } from "./modules";

const m = (name: string, requires: string[] = []): ModuleInfo => ({
  name, title: name.toUpperCase(), description: "", kind: "label", scope: "row", requires,
  columns: [], engine: null, engine_kind: "local", default_on: true,
});
const MODULES = [m("language"), m("ner"), m("entity_resolution", ["ner"]), m("relations", ["entity_resolution"]),
                 m("event"), m("event_coreference", ["event", "entity_resolution"]), m("custom")];

describe("module selection", () => {
  it("selecting a module brings in its requirements, in catalog order", () => {
    expect(withRequirements(["language"], "relations", MODULES)).toEqual(["language", "ner", "entity_resolution", "relations"]);
  });
  it("deselecting a module drops everything that needs it", () => {
    const all = MODULES.map((x) => x.name);
    expect(withoutDependents(all, "ner", MODULES)).toEqual(["language", "event", "custom"]);
  });
  it("explains why a module is locked in", () => {
    expect(requiredBy(["ner", "entity_resolution"], "ner", MODULES)).toEqual(["ENTITY_RESOLUTION"]);
  });
  it("puts unknown modules in a catch-all group instead of hiding them", () => {
    expect(groupModules(MODULES).at(-1)).toEqual({ title: "More", items: [MODULES[6]] });
  });
});
