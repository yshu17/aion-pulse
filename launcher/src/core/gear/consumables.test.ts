import { describe, expect, it } from "vitest";

import table from "../../../../data/consumables/consumables.json";
import { chosenConsumables, consumableLines, consumableTotals, filterConsumables, putConsumable, STAT_KEY, type Consumable } from "./consumables";

const item = (id: number, name: string, kind: Consumable["kind"], stats: [string, number, boolean][], more: Partial<Consumable> = {}): Consumable =>
  ({ id, ids: [id], name, kind, grade: "common", icon: "i", item_level: 1, use_level: null, minutes: 30, stats, unknown: [], ...more });

const list = [
  item(1, "Омлет", "food", [["Макс. HP", 40, false], ["Физ. крит.", 10, false]]),
  item(2, "Суп", "food", [["Макс. HP", 40, false], ["Физ. крит.", 10, false]]),
  item(3, "Ёрш в тесте", "food", [["Макс. HP", 36, false]], { ids: [3, 33] }),
  item(4, "[Ивент] Пирог", "food", [["Физ. крит.", 12, false]]),
  item(5, "Сок", "drink", [["Макс. HP", 40, false], ["Скорость атаки", 5, true]]),
];

describe("the food and drinks of the gear calculator", () => {
  it("knows an engine key for every stat of the collected data", () => {
    const named = new Set((table.items as unknown as Consumable[]).flatMap((x) => x.stats.map((s) => s[0])));
    expect([...named].filter((name) => !STAT_KEY[name])).toEqual([]);
  });

  it("takes one of each kind, found by any of its item ids, and drops what the data no longer has", () => {
    expect(chosenConsumables({ drink: 5, food: 33, candy: 999 }, list).map((x) => x.name)).toEqual(["Ёрш в тесте", "Сок"]);
    expect(chosenConsumables({ food: 5 }, list)).toEqual([]); // a drink does not sit in the food slot
    expect(chosenConsumables(undefined, list)).toEqual([]);
  });

  it("puts one into its own slot and takes it off", () => {
    expect(putConsumable({ drink: 5 }, "food", 1)).toEqual({ drink: 5, food: 1 });
    expect(putConsumable({ drink: 5, food: 1 }, "food", null)).toEqual({ drink: 5 });
  });

  it("gives the arithmetic the engine's keys, and adds equal stats up for the summary", () => {
    const both = chosenConsumables({ food: 1, drink: 5 }, list);
    expect(consumableLines(both)).toEqual([["maxhp", 40, false], ["critical", 10, false], ["maxhp", 40, false], ["attackdelay", 5, true]]);
    expect(consumableTotals(both)).toEqual([["Макс. HP", 80, false], ["Физ. крит.", 10, false], ["Скорость атаки", 5, true]]);
  });

  it("lists a kind with its stat chips, the strongest of the chosen stat first", () => {
    const found = filterConsumables(list, { kind: "food", stat: "Физ. крит.", query: "", noEvent: false, same: false });
    expect(found.rows.map((r) => r.item.name)).toEqual(["[Ивент] Пирог", "Омлет", "Суп"]);
    expect(found.stats).toEqual([["Макс. HP", 3], ["Физ. крит.", 3]]);
    expect(found.total).toBe(4);
    expect(found.matched).toBe(3);
  });

  it("puts equal effects into one row, hides the event ones and searches with «ё» as «е»", () => {
    const same = filterConsumables(list, { kind: "food", stat: "", query: "", noEvent: true, same: true });
    expect(same.rows.map((r) => [r.item.name, r.more])).toEqual([["Ёрш в тесте", 0], ["Омлет", 1]]);
    expect(same.total).toBe(3);
    expect(filterConsumables(list, { kind: "food", stat: "", query: "ерш", noEvent: false, same: false }).rows.map((r) => r.item.id)).toEqual([3]);
  });

  it("forgets a stat chip the kind does not have", () => {
    const found = filterConsumables(list, { kind: "drink", stat: "Физ. крит.", query: "", noEvent: false, same: true });
    expect(found.stat).toBe("");
    expect(found.rows.map((r) => r.item.id)).toEqual([5]);
  });
});
