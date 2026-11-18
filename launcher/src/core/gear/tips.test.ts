import { describe, expect, it } from "vitest";

import { durationText, effectLines } from "./tips";

const stat = (name: string, value: number, relative = false, remain = 180000) =>
  ({ id: 1, type: "statup", remain_time: remain, stats: [{ name, value: { value, relative } }] });

describe("the lines a buff's tooltip shows", () => {
  it("names each stat with its number, a relative one as a percent, and puts a plus in front of a gain", () => {
    expect(effectLines([stat("maxhp", 2500), stat("flyspeed", 10, true)])).toEqual(["HP +2 500", "Скор. полёта +10%"]);
    expect(effectLines([stat("physicaldefend", -100)])).toEqual(["Физ. защита −100"]);
  });

  it("shows a stat once when the data repeats it", () => {
    expect(effectLines([stat("maxhp", 100), stat("maxhp", 100), stat("maxhp", 200)])).toEqual(["HP +100", "HP +200"]);
  });

  it("says an instant heal and skips what it cannot name", () => {
    expect(effectLines([{ type: "heal_instant", value: { value: 25, relative: true } }, { type: "weird" }])).toEqual(["Мгновенное лечение 25%"]);
  });
});

describe("how long it lasts", () => {
  it("is written in hours, minutes and seconds, empty for nothing", () => {
    expect(durationText(180000)).toBe("3 мин");
    expect(durationText(90000)).toBe("1 мин 30 с");
    expect(durationText(3600000)).toBe("1 ч");
    expect(durationText(15000)).toBe("15 с");
    expect(durationText(0)).toBe("");
    expect(durationText(undefined)).toBe("");
  });

  it("is the longest time among the effects", () => {
    expect(effectLines([stat("maxhp", 1, false, 60000), stat("maxmp", 1, false, 300000)], true).at(-1)).toBe("Длительность: 5 мин");
  });
});
