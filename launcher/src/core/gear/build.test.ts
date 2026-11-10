import { describe, expect, it } from "vitest";

import { addSet, emptyBuild, readBuild, removeSet, withSet, writeBuild } from "./build";

describe("a saved gear build", () => {
  it("reads back what was written, and a broken text gives the default build", () => {
    const b = withSet(emptyBuild(), 0, (s) => ({ ...s, slots: { main: { id: 1, enchant: 10, stones: [5, null] } } }));
    expect(readBuild(writeBuild(b))).toEqual(b);
    expect(readBuild("{oops")).toEqual(emptyBuild());
    expect(readBuild(null)).toEqual(emptyBuild());
    expect(readBuild(JSON.stringify({ ...b, level: 99, active: 7 })).level).toBe(55); // the level and the active set stay in range
  });

  it("adds a set as a copy of the active one, at most four, and removes one keeping the active set in range", () => {
    let b = withSet(emptyBuild(), 0, (s) => ({ ...s, slots: { head: { id: 2, enchant: 0, stones: [] } } }));
    b = addSet(b);
    expect(b.sets.map((s) => s.title)).toEqual(["Набор 1", "Набор 2"]);
    expect(b.sets[1].slots.head?.id).toBe(2);
    expect(b.active).toBe(1);
    b = addSet(addSet(addSet(b)));
    expect(b.sets.length).toBe(4);
    b = removeSet(b, 0);
    expect(b.sets.map((s) => s.title)).toEqual(["Набор 1", "Набор 2", "Набор 3"]);
    expect(b.active).toBe(2);
    expect(removeSet(emptyBuild(), 0).sets.length).toBe(1);
  });
});
