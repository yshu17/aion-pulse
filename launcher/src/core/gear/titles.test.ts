import { describe, expect, it } from "vitest";

import { findTitles, titleSide, titleSummary } from "./titles";

const title = (id: number, name: string, bonus: string[]) => ({ id, name, race: "pc_light,pc_dark", bonus, icon: "" });
const TITLES = [
  title(1, "Охотник снежной долины", ["HitAccuracy 9", "Critical 7"]),
  title(2, "Путешественник Атреи", ["speed 4%", "maxHp 60"]),
  title(3, "Ёж пустыни", ["flyspeed 2%"]),
];

describe("a title's side", () => {
  it("names both sides, one side, or nothing", () => {
    expect(titleSide("pc_light,pc_dark")).toBe("Обе стороны");
    expect(titleSide("pc_light")).toBe("Элийцы");
    expect(titleSide("pc_dark")).toBe("Асмодиане");
    expect(titleSide("")).toBe("");
  });
});

describe("a title's bonuses in words", () => {
  it("says them as «База данных» does, not as the client's keys", () => {
    expect(titleSummary(["HitAccuracy 9", "speed 4%"])).toBe("Точность +9, Скорость движения +4%");
  });
});

describe("searching titles", () => {
  it("finds by the name and by a bonus in words, ignoring case and «ё»", () => {
    expect(findTitles(TITLES, "крит").map((t) => t.id)).toEqual([1]);
    expect(findTitles(TITLES, "еж пуст").map((t) => t.id)).toEqual([3]);
    expect(findTitles(TITLES, "АТРЕИ").map((t) => t.id)).toEqual([2]);
    expect(findTitles(TITLES, "скорость").map((t) => t.id)).toEqual([2, 3]);
  });

  it("returns everything for an empty search, cut to the limit", () => {
    expect(findTitles(TITLES, "").map((t) => t.id)).toEqual([1, 2, 3]);
    expect(findTitles(TITLES, "", 2).map((t) => t.id)).toEqual([1, 2]);
  });
});
