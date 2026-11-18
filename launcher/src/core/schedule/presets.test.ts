import { describe, expect, it } from "vitest";

import { addPreset, emptyState, MAX_PRESETS, readPresets, removePreset, renamePreset, switchPreset, writePresets, type ScheduleState } from "./presets";

const state = (name: string): ScheduleState => ({
  custom: { added: [{ day: "fri", start: "19:30", end: "20:30", name }], removed: ["mon|02:00|Дер"] },
  remind: [`fri|19:30|${name}`], leads: { [`fri|19:30|${name}`]: 15 }, hidden: ["Арены"],
  resets: { edits: {}, removed: [], own: [] },
});

describe("schedule presets (sets like the gear calculator's)", () => {
  it("start with one set, «Набор 1», that is the schedule as it is", () => {
    expect(readPresets(null)).toEqual({ active: 0, presets: [{ title: "Набор 1", state: null }] });
    expect(readPresets("{broken")).toEqual(readPresets(null));
  });

  it("come back from the file as they were written", () => {
    const store = addPreset(readPresets(null), state("Рейд"));
    expect(readPresets(writePresets(store))).toEqual(store);
  });

  it("drop wrong entries of the file and keep the active one in range", () => {
    const text = JSON.stringify({ active: 7, presets: [{ title: "", state: { custom: "x" } }, { title: "Твинк", state: state("Фарм") }, 5] });
    const store = readPresets(text);
    expect(store.presets.map((p) => p.title)).toEqual(["Набор 1", "Твинк"]);
    expect(store.presets[0].state).toBeNull();
    expect(store.active).toBe(1);
  });

  it("add a copy of the schedule as it is now, at most four, and switch to it", () => {
    let store = addPreset(readPresets(null), state("Рейд"));
    expect(store.active).toBe(1);
    expect(store.presets.map((p) => p.title)).toEqual(["Набор 1", "Набор 2"]);
    expect(store.presets[0].state).toEqual(state("Рейд")); // the one left keeps what it had
    expect(store.presets[1].state).toEqual(state("Рейд"));
    for (let i = 0; i < 5; i++) store = addPreset(store, state("Рейд"));
    expect(store.presets).toHaveLength(MAX_PRESETS);
  });

  it("switch: the schedule now is kept in the set left, the chosen set's schedule is what to load", () => {
    const store = addPreset(readPresets(null), state("Рейд"));
    const { store: back, load } = switchPreset(store, 0, state("Осада"));
    expect(back.active).toBe(0);
    expect(back.presets[1].state).toEqual(state("Осада"));
    expect(load).toEqual(state("Рейд"));
    expect(switchPreset(back, 0, state("Х")).load).toBeNull(); // the set that is on: nothing to load
  });

  it("remove: the other sets keep their names, the active one moves to a neighbour and is loaded", () => {
    let store = addPreset(readPresets(null), state("А"));
    store = addPreset(store, state("Б"));
    store = renamePreset(store, 2, "Твинк");
    const { store: after, load } = removePreset(store, 2, state("В"));
    expect(after.presets.map((p) => p.title)).toEqual(["Набор 1", "Набор 2"]);
    expect(after.active).toBe(1);
    expect(load).toEqual(state("Б"));
    const kept = removePreset(after, 0, state("Г")); // not the active one: the schedule stays
    expect(kept.load).toBeNull();
    expect(kept.store.active).toBe(0);
    expect(kept.store.presets.map((p) => p.title)).toEqual(["Набор 1"]);
    expect(removePreset(kept.store, 0, state("Д")).store).toEqual(kept.store); // the last set stays
  });

  it("rename: a trimmed name of up to 24 letters, an empty one is refused", () => {
    const store = readPresets(null);
    expect(renamePreset(store, 0, "  Основа  ").presets[0].title).toBe("Основа");
    expect(renamePreset(store, 0, "   ")).toBe(store);
    expect(renamePreset(store, 0, "x".repeat(40)).presets[0].title).toHaveLength(24);
  });

  it("keep each set's own schedule link, none at all too, and drop a broken one", () => {
    const withLink = { ...state("Рейд"), source: { url: "https://example.com/s.png", known: "abc" } };
    const noLink = { ...state("Твинк"), source: { url: "", known: null } };
    let store = addPreset(readPresets(null), withLink);
    const { store: next, load } = switchPreset(store, 0, noLink); // set 2 is left without a link, set 1 kept its own
    expect(load?.source).toEqual({ url: "https://example.com/s.png", known: "abc" });
    const back = readPresets(writePresets(next));
    expect(back.presets[0].state?.source).toEqual({ url: "https://example.com/s.png", known: "abc" });
    expect(back.presets[1].state?.source).toEqual({ url: "", known: null });
    const broken = readPresets(JSON.stringify({ active: 0, presets: [{ title: "A", state: { ...state("X"), source: { url: 5 } } }] }));
    expect(broken.presets[0].state?.source).toBeUndefined();
  });

  it("an empty schedule: no own events, no reminders, nothing hidden", () => {
    expect(emptyState()).toEqual({ custom: { added: [], removed: [] }, remind: [], leads: {}, hidden: [], resets: { edits: {}, removed: [], own: [] } });
  });
});
