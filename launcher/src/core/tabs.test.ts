import { describe, expect, it } from "vitest";

import { BETA, LIVE_TABS, TOP, isBeta, menuOf, tabLabel } from "./tabs";

describe("the top tabs (docs/concepts/top-tabs, variant 2)", () => {
  it("are three groups: places, two menus, guides; NPC is a tab of its own beside the map", () => {
    expect(TOP.map((group) => group.map((tab) => tab.label))).toEqual([
      ["Чат", "Карта", "NPC", "Расписание"],
      ["Калькуляторы", "База данных"],
      ["Гайды"],
    ]);
  });

  it("put the calculators and the database's ten sections in menus, sections under their headings", () => {
    const [, [calc, db]] = TOP;
    expect(calc.menu!.map((g) => [g.title, g.items.map((s) => s.label)])).toEqual([["", ["Экипировка", "Стигмы", "Крафт"]]]);
    expect(db.menu!.map((g) => [g.title, g.items.map((s) => s.label)])).toEqual([
      ["Предметы", ["Предметы", "Оружие", "Броня", "Украшения"]],
      ["Знания", ["Книги умений", "Стигмы", "Титулы", "Питомцы"]],
      ["Мир", ["Задания", "Рецепты"]],
    ]);
  });

  it("give every screen its own id: the calculator's «Броня» is not the database's", () => {
    const ids = TOP.flat().flatMap((tab) => (tab.menu ? tab.menu.flatMap((g) => g.items.map((s) => s.id)) : [tab.id]));
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toContain("calc:Экипировка");
    expect(ids).toContain("db:Броня");
  });

  it("name a screen and the menu it lies in", () => {
    expect(tabLabel("db:Оружие")).toBe("Оружие");
    expect(tabLabel("NPC")).toBe("NPC");
    expect(menuOf("db:Оружие")).toBe("База данных");
    expect(menuOf("calc:Крафт")).toBe("Калькуляторы");
    expect(menuOf("Карта")).toBeNull();
  });

  it("have screens only for the chat, the map, the NPCs and the schedule", () => {
    expect(LIVE_TABS).toEqual(["Чат", "Карта", "NPC", "Расписание", "calc:Экипировка"]);
  });

  it("mark the database and the gear calculator as beta, and nothing else", () => {
    expect([...BETA].sort()).toEqual(["calc:Экипировка", "db"]);
    expect(isBeta("db")).toBe(true);
    expect(isBeta("db:Оружие")).toBe(true); // every section of the database
    expect(isBeta("calc:Экипировка")).toBe(true);
    for (const id of ["Чат", "Карта", "NPC", "Расписание", "calc:Стигмы", "calc:Крафт", "Гайды"]) expect(isBeta(id)).toBe(false);
  });
});
