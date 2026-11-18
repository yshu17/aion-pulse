import { describe, expect, it } from "vitest";

import { add, bestLevel, canAdd, cost, emptyPick, needsOf, refit, remove, slotsAt, type Ctx, type Stigma } from "./calc";

const st = (id: string, advanced: boolean, levels: [number, number | null, number][]): Stigma => ({
  id, faction: "daeva", advanced, kind: "Normal", target: "", info: [],
  levels: levels.map(([level, shards, ap], i) => ({ level, skill: i + 1, name: id, text: "", mp: "", cast: "", cooldown: "", shards, ap })),
});

// a: normal 20/30, b: normal 40, c: advanced 45 needs a and b, d: advanced 50 needs c, e: normal 52
const STIGMAS = [st("a", false, [[20, 10, 0], [30, 20, 0]]), st("b", false, [[40, 30, 0]]), st("c", true, [[45, 100, 1000]]),
  st("d", true, [[50, 200, 5000]]), st("e", false, [[52, null, 0]])];
const ctx = (level: number): Ctx => ({ stigmas: new Map(STIGMAS.map((s) => [s.id, s])), needs: [["c", "a"], ["c", "b"], ["d", "c"]], level });

describe("stigma slots by the character's level (the calculator's slots_calc)", () => {
  it("opens normal slots at 20, 20, 30, 40, 50, 55 and advanced ones at 45, 45, 50, 52, 55", () => {
    expect(slotsAt(19)).toEqual({ normal: 0, advanced: 0 });
    expect(slotsAt(20)).toEqual({ normal: 2, advanced: 0 });
    expect(slotsAt(45)).toEqual({ normal: 4, advanced: 2 });
    expect(slotsAt(55)).toEqual({ normal: 6, advanced: 5 });
  });
});

describe("a stigma's level", () => {
  it("is the highest the character can wear, or null below the first", () => {
    expect(bestLevel(STIGMAS[0], 35)).toBe(30);
    expect(bestLevel(STIGMAS[1], 35)).toBeNull();
  });
});

describe("dependencies", () => {
  it("lists every stigma needed first, deepest first, without the stigma itself", () => {
    expect(needsOf(ctx(55).needs, "d")).toEqual(["a", "b", "c"]);
    expect(needsOf(ctx(55).needs, "a")).toEqual([]);
  });
});

describe("adding a stigma", () => {
  it("puts it and what it needs into the slots: normal ones first into normal slots, the rest into advanced", () => {
    const pick = add(ctx(55), emptyPick(), "d");
    expect(pick.normal).toEqual(["a", "b"]);
    expect(pick.advanced).toEqual(["c", "d"]);
    expect(pick.levels).toEqual({ a: 30, b: 40, c: 45, d: 50 });
  });

  it("moves normal stigmas into free advanced slots when the normal ones are full", () => {
    const full = { normal: ["x1", "x2", "x3", "x4", "x5"], advanced: [], levels: {} };
    const pick = add(ctx(50), full, "c");
    expect(pick.normal).toEqual(full.normal);
    expect(pick.advanced).toEqual(["a", "b", "c"]);
    // at 45 there are two advanced slots: c and its two needs do not fit
    expect(canAdd(ctx(45), { ...full, normal: full.normal.slice(0, 4) }, "c")).toBe(false);
  });

  it("refuses a stigma the character is too low for, or one whose needs are too high", () => {
    expect(canAdd(ctx(35), emptyPick(), "b")).toBe(false);
    expect(canAdd(ctx(44), emptyPick(), "c")).toBe(false);
    expect(add(ctx(35), emptyPick(), "b")).toEqual(emptyPick());
  });

  it("refuses one already picked", () => {
    const pick = add(ctx(55), emptyPick(), "a");
    expect(canAdd(ctx(55), pick, "a")).toBe(false);
  });
});

describe("removing a stigma", () => {
  it("takes away the stigmas that need it too", () => {
    const pick = remove(ctx(55), add(ctx(55), emptyPick(), "d"), "a");
    expect(pick.normal).toEqual(["b"]);
    expect(pick.advanced).toEqual([]);
    expect(pick.levels).toEqual({ b: 40 });
  });
});

describe("refit after the level changes", () => {
  it("keeps what still fits and lowers stigma levels to the character's", () => {
    const pick = add(ctx(55), add(ctx(55), emptyPick(), "d"), "e");
    const lower = refit(ctx(46), pick);
    expect(lower.normal).toEqual(["a", "b"]);
    expect(lower.advanced).toEqual(["c"]);
    expect(lower.levels).toEqual({ a: 30, b: 40, c: 45 });
  });

  it("keeps a chosen lower stigma level", () => {
    const pick = add(ctx(55), emptyPick(), "a");
    expect(refit(ctx(55), { ...pick, levels: { a: 20 } }).levels).toEqual({ a: 20 });
  });
});

describe("the cost", () => {
  it("adds up shards and abyss points of the chosen levels and says when one is unknown", () => {
    expect(cost(ctx(55), add(ctx(55), emptyPick(), "d"))).toEqual({ shards: 20 + 30 + 100 + 200, ap: 6000, unknown: false });
    expect(cost(ctx(55), add(ctx(55), emptyPick(), "e"))).toEqual({ shards: 0, ap: 0, unknown: true });
  });
});
