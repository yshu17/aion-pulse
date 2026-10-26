import { describe, expect, it } from "vitest";

import { checkReset, nextOwnId, parseResets, resetEvents, resolveResets, serializeResets } from "./resets";

const BASE = [
  { name: "Откат квестов", when: "daily", time: "09:00" },
  { name: "Откат недели", when: "weekly", day: "wed", time: "09:00" },
];

describe("resets", () => {
  it("shows the server resets as they are, then with the user's time and own ones", () => {
    expect(resolveResets(BASE, parseResets(null)).map((r) => [r.id, r.time, r.own, r.edited])).toEqual([["r0", "09:00", false, false], ["r1", "09:00", false, false]]);
    const store = parseResets('{"edits":{"r1":{"time":"08:30","day":"thu"},"r9":{"time":"xx"}},"own":[{"id":"own1","name":" Рейд ","when":"weekly","day":"fri","time":"20:00"}]}');
    const out = resolveResets(BASE, store);
    expect(out[1]).toMatchObject({ time: "08:30", day: "thu", edited: true });
    expect(out[2]).toMatchObject({ id: "own1", name: "Рейд", own: true, day: "fri" });
  });

  it("drops broken entries and survives a broken file", () => {
    expect(parseResets("не json")).toEqual({ edits: {}, own: [] });
    const store = parseResets('{"edits":{"r0":{"time":"25:00"}},"own":[{"id":"a","name":"","when":"daily","time":"10:00"},{"id":"b","name":"X","when":"weekly","time":"10:00"}]}');
    expect(store).toEqual({ edits: {}, own: [] });
    expect(parseResets(serializeResets({ edits: { r0: { time: "07:00" } }, own: [] })).edits.r0.time).toBe("07:00");
  });

  it("makes seven occurrences of a daily reset and one of a weekly, one minute long", () => {
    expect(resetEvents({ name: "A", when: "daily", time: "09:00" })).toHaveLength(7);
    expect(resetEvents({ name: "A", when: "weekly", day: "wed", time: "23:59" })).toEqual([{ day: "wed", start: "23:59", end: "24:00", name: "A", kind: "Откат" }]);
  });

  it("checks a new reset and numbers own ones", () => {
    expect(checkReset({ name: "", when: "daily", time: "09:00" })).not.toBe("");
    expect(checkReset({ name: "A", when: "daily", time: "9:00" })).not.toBe("");
    expect(checkReset({ name: "A", when: "weekly", time: "09:00" })).not.toBe("");
    expect(checkReset({ name: "A", when: "weekly", day: "mon", time: "09:00" })).toBe("");
    expect(nextOwnId({ edits: {}, own: [{ id: "own3", name: "A", when: "daily", time: "10:00" }] })).toBe("own4");
  });
});
