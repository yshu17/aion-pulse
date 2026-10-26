import { describe, expect, it } from "vitest";

import { checkReset, daysText, EMPTY_RESETS, nextOwnId, parseResets, removeReset, resetEvents, resolveResets, restoreResets, saveReset, serializeResets } from "./resets";

const BASE = [
  { name: "Откат квестов", when: "daily", time: "09:00" },
  { name: "Откат недели", when: "weekly", day: "wed", time: "09:00" },
];
const ALL = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

describe("resets", () => {
  it("shows the server resets with their days", () => {
    expect(resolveResets(BASE, EMPTY_RESETS).map((r) => [r.id, r.days.length, r.own, r.edited])).toEqual([["r0", 7, false, false], ["r1", 1, false, false]]);
  });

  it("renames, moves to other days and changes the time of a server reset; the original drops the edit", () => {
    let store = saveReset(BASE, EMPTY_RESETS, "r1", { name: " Недельный ", days: ["thu", "mon"], time: "08:30" });
    expect(resolveResets(BASE, store)[1]).toMatchObject({ name: "Недельный", days: ["mon", "thu"], time: "08:30", edited: true });
    store = saveReset(BASE, store, "r1", { name: "Откат недели", days: ["wed"], time: "09:00" });
    expect(store.edits).toEqual({});
  });

  it("hides a server reset until restored, deletes an own one", () => {
    let store = saveReset(BASE, EMPTY_RESETS, null, { name: "Рейд", days: ["fri"], time: "20:00" });
    expect(store.own).toEqual([{ id: "own1", name: "Рейд", days: ["fri"], time: "20:00" }]);
    store = removeReset(removeReset(store, "r0"), "own1");
    expect(resolveResets(BASE, store).map((r) => r.id)).toEqual(["r1"]);
    expect(resolveResets(BASE, restoreResets(store)).map((r) => r.id)).toEqual(["r0", "r1"]);
  });

  it("reads its file, the first format too, and survives a broken one", () => {
    expect(parseResets("не json")).toEqual(EMPTY_RESETS);
    const old = parseResets('{"edits":{"r1":{"time":"08:30","day":"thu"},"r0":{"time":"25:00"}},"own":[{"id":"own1","name":"Рейд","when":"weekly","day":"fri","time":"20:00"},{"id":"b","name":"X","when":"weekly","time":"10:00"}]}', BASE);
    expect(old.edits).toEqual({ r1: { name: "Откат недели", days: ["thu"], time: "08:30" } });
    expect(old.own).toEqual([{ id: "own1", name: "Рейд", days: ["fri"], time: "20:00" }]);
    const store = saveReset(BASE, removeReset(EMPTY_RESETS, "r0"), "r1", { name: "A", days: ["sun"], time: "07:00" });
    expect(parseResets(serializeResets(store), BASE)).toEqual(store);
  });

  it("makes one one-minute occurrence per day", () => {
    expect(resetEvents({ name: "A", days: ALL, time: "09:00" })).toHaveLength(7);
    expect(resetEvents({ name: "A", days: ["wed"], time: "23:59" })).toEqual([{ day: "wed", start: "23:59", end: "24:00", name: "A", kind: "Откат" }]);
  });

  it("checks a draft, names the days, numbers own ones", () => {
    expect(checkReset({ name: "", days: ["mon"], time: "09:00" })).not.toBe("");
    expect(checkReset({ name: "A", days: [], time: "09:00" })).not.toBe("");
    expect(checkReset({ name: "A", days: ["mon"], time: "9:00" })).not.toBe("");
    expect(checkReset({ name: "A", days: ["mon"], time: "09:00" })).toBe("");
    expect(daysText(ALL)).toBe("Каждый день");
    expect(daysText(["thu", "mon"])).toBe("Пн, Чт");
    expect(nextOwnId({ ...EMPTY_RESETS, own: [{ id: "own3", name: "A", days: ["mon"], time: "10:00" }] })).toBe("own4");
  });
});
