import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import { questNames, questsOf, recipe, recipesFor, recipesUsing, vendorItems } from "./game";
import type { All } from "./npcPoints";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");

/** A small pulse.db in memory with the real schema: two quests of NPC 100, a recipe of a sword, a merchant. */
function sample(): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  db.exec(`
    INSERT INTO item (id, name, name_key, grade, icon) VALUES
      (901, 'Древний меч', 'древний меч', 'unique', 'icon_sword'), (902, 'Железо', 'железо', 'common', 'icon_ore'),
      (907, 'Кожа', 'кожа', 'common', NULL);
    INSERT INTO quest (id, name, name_key, min_level, max_level, race, category, repeatable, giver, ender, rewards) VALUES
      (1101, 'Ёлочный сбор', 'елочный сбор', 1, 0, 'pc_light', 'quest | Элтнен', 0, '100', NULL, '[{"type":"item","item":"901","amount":1}]'),
      (1102, 'Сдать отчёт', 'сдать отчет', 10, 20, 'pc_light,pc_dark', NULL, 1, NULL, '100', '[]'),
      (1200, 'Только в ссылках', 'только в ссылках', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);
    INSERT INTO recipe VALUES (155000078, 'Древний меч', 'древний меч', 901, 1, 'weaponsmith', 10, 'pc_light', '[100200209]');
    INSERT INTO recipe_part VALUES (155000078, 0, 902, 3), (155000078, 1, 907, 5), (155000078, 2, 999, 1);
    INSERT INTO vendor_item VALUES ('400', 902, 'trade_info'), ('400', 901, 'abyss_trade_info');
  `);
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("quests, recipes and vendors from pulse.db", () => {
  it("names every quest for chat links", async () => {
    expect(await questNames(sample())).toEqual({ "1101": "Ёлочный сбор", "1102": "Сдать отчёт", "1200": "Только в ссылках" });
  });

  it("gives the quests an NPC gives and takes back, with their rewards", async () => {
    const quests = await questsOf(sample(), "100");
    expect(quests.map((q) => [q.id, q.role])).toEqual([["1101", "giver"], ["1102", "ender"]]);
    expect(quests[0]).toMatchObject({ name: "Ёлочный сбор", min_level: 1, max_level: 0, races: ["pc_light"], repeatable: false,
      rewards: [{ type: "item", item: "901", amount: 1 }] });
    expect(quests[1]).toMatchObject({ races: ["pc_light", "pc_dark"], repeatable: true, category: "" });
    expect(await questsOf(sample(), "nobody")).toEqual([]);
  });

  it("gives a recipe with its parts named, the recipes of an item and the recipes it goes into", async () => {
    const all = sample();
    const sword = await recipe(all, "155000078");
    expect(sword).toMatchObject({ id: "155000078", name: "Древний меч", product: { id: "901", name: "Древний меч", grade: "unique", icon: "icon_sword" },
      count: 1, profession: "weaponsmith", level: 10, race: "pc_light", combo: ["100200209"] });
    expect(sword!.parts).toEqual([
      { id: "902", name: "Железо", grade: "common", icon: "icon_ore", count: 3 },
      { id: "907", name: "Кожа", grade: "common", icon: "", count: 5 },
      { id: "999", name: "", grade: "", icon: "", count: 1 }, // an item the database does not name
    ]);
    expect((await recipesFor(all, "901")).map((r) => r.id)).toEqual(["155000078"]);
    expect((await recipesUsing(all, "907")).map((r) => r.id)).toEqual(["155000078"]);
    expect(await recipe(all, "1")).toBeNull();
  });

  it("gives what a merchant trades by the client's lists", async () => {
    expect(await vendorItems(sample(), "400")).toEqual([
      { id: "901", name: "Древний меч", grade: "unique", icon: "icon_sword", kind: "abyss_trade_info" },
      { id: "902", name: "Железо", grade: "common", icon: "icon_ore", kind: "trade_info" },
    ]);
  });
});
