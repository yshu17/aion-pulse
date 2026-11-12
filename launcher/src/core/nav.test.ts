import { describe, expect, it } from "vitest";

import { MAX_TRAIL, back, visit } from "./nav";

describe("the way back", () => {
  it("adds the screen left, not the same screen twice in a row, and goes back one step at a time", () => {
    let trail: string[] = [];
    trail = visit(trail, "Чат", "db:Задания");
    trail = visit(trail, "db:Задания", "NPC");
    trail = visit(trail, "NPC", "NPC"); // nothing changed
    expect(trail).toEqual(["Чат", "db:Задания"]);
    let at: string | null;
    [at, trail] = back(trail);
    expect(at).toBe("db:Задания");
    [at, trail] = back(trail);
    expect(at).toBe("Чат");
    expect(back(trail)).toEqual([null, []]);
  });

  it("keeps the last screens only", () => {
    let trail: string[] = [];
    for (let i = 0; i < MAX_TRAIL + 10; i++) trail = visit(trail, `a${i}`, `a${i + 1}`);
    expect(trail).toHaveLength(MAX_TRAIL);
    expect(trail[trail.length - 1]).toBe(`a${MAX_TRAIL + 9}`);
  });
});
