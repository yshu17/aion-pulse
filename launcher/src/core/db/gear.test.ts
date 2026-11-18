import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import { gearChoices, gearGroups, gearItem, gearSets, gearStones, skillText } from "./gear";
import type { All } from "./npcPoints";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");

function sample(): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  db.exec(`
    INSERT INTO gear_item (id, name, name_key, icon, grade, level, slot, grp, races, classes, basic, bonus, stones, stones_bonus, enchant, set_id) VALUES
      (1, 'Копье', 'копье', 'i1', 'epic', 55, 'main', 'polearm', 'pc_light,pc_dark', '["fighter"]', '{"mindamage":285}', '[["maxhp",347,false]]', 5, 0, 1, NULL),
      (2, 'Меч', 'меч', 'i2', 'rare', 50, 'main_or_sub', 'sword', 'pc_light', '["fighter","knight"]', '{}', '[]', NULL, NULL, 1, NULL),
      (3, 'Щит', 'щит', 'i3', 'epic', 50, 'sub', 'shield', '', '["knight"]', '{"block":926}', '[]', 3, 1, 1, NULL),
      (4, 'Кираса', 'кираса', 'i4', 'epic', 55, 'torso', 'pl_torso', '', '["fighter","knight"]', '{}', '[]', 6, 1, 1, 7),
      (5, 'Ёлочный меч', 'елочный меч', 'i5', 'common', 10, 'main_or_sub', 'sword', '', '["fighter"]', '{}', '[]', NULL, NULL, 0, NULL);
    INSERT INTO gear_stone (id, name, icon, grade, level, stat, value) VALUES (10, 'Камень HP', 's', 'common', 10, 'maxhp', 20), (11, 'Камень HP', 's', 'rare', 50, 'maxhp', 60);
    INSERT INTO gear_set (id, name, items, bonuses) VALUES (7, 'Набор', '[4,8]', '[{"need":2,"stats":[["maxhp",100,false]]}]');
  `);
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("the gear calculator's data", () => {
  it("lists what fits a slot for a class, newest first, and parses the item", async () => {
    const all = sample();
    expect((await gearChoices(all, "main", { cls: "fighter" })).map((i) => i.id)).toEqual([1, 2, 5]);
    expect((await gearChoices(all, "sub", { cls: "knight" })).map((i) => i.id)).toEqual([3, 2]); // a shield or a one-handed weapon
    expect((await gearChoices(all, "main", { cls: "fighter", levelMin: 20, grade: "rare" })).map((i) => i.id)).toEqual([2]);
    expect((await gearChoices(all, "main", { query: "ЕЛОЧ" })).map((i) => i.id)).toEqual([5]);
    expect(await gearGroups(all, "main", "fighter")).toEqual(["polearm", "sword"]);
    expect(await gearItem(all, 1)).toMatchObject({ grp: "polearm", basic: { mindamage: 285 }, bonus: [["maxhp", 347, false]], stones: 5, enchant: true, setId: null });
    expect((await gearItem(all, 5))!.enchant).toBe(false);
  });

  it("gives the stones under a level and the sets by id", async () => {
    const all = sample();
    expect((await gearStones(all, 40)).map((s) => s.id)).toEqual([10]);
    expect(await gearSets(all, [7, 7])).toEqual([{ id: 7, name: "Набор", items: [4, 8], bonuses: [{ need: 2, stats: [["maxhp", 100, false]] }] }]);
  });
});

describe("a skill's text by name", () => {
  it("takes the resolved text with the server's numbers, else the description, null when unknown", async () => {
    const db = new DatabaseSync(":memory:");
    db.exec(SCHEMA);
    db.exec(`INSERT INTO skill (id, internal_name, name, name_key, description, icon, stigma) VALUES
      (1, 'KN_StoneBody_G1', 'Каменное тело I', 'каменное тело i', 'Восстанавливает [%e1.Value] HP.', NULL, 0),
      (2, 'P_Other_G1', 'Усиление I', 'усиление i', 'Увеличивает силу.', NULL, 0);
      INSERT INTO skill_damage (skill_id, text, dmg_min, dmg_max) VALUES (1, 'Восстанавливает 25% HP.', NULL, NULL);`);
    const all: All = async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
    expect(await skillText(all, "Каменное тело I")).toBe("Восстанавливает 25% HP.");
    expect(await skillText(all, "Усиление I")).toBe("Увеличивает силу.");
    expect(await skillText(all, "Нет такого")).toBeNull();
  });
});
