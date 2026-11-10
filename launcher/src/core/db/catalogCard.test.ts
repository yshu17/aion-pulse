import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import { entityCard, itemSkill, itemSources } from "./catalogCard";
import type { All } from "./npcPoints";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");

/** The ids packed as steps (core/pulse_db/build.py pack_ids, delta=True). */
function pack(ids: number[]): Uint8Array {
  const out: number[] = [];
  let last = 0;
  for (const id of ids) {
    let n = id - last;
    last = id;
    while (n >= 0x80) { out.push((n & 0x7f) | 0x80); n = Math.floor(n / 0x80); }
    out.push(n);
  }
  return Uint8Array.from(out);
}

function sample(): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  db.exec(`
    INSERT INTO npc (id, name, name_key, source) VALUES ('100', 'Кабан', 'кабан', 'client'), ('200', 'Волк', 'волк', 'client'),
      ('300', 'Торговец', 'торговец', 'client');
    INSERT INTO item (id, name, name_key) VALUES (1, 'Меч', 'меч'), (2, 'Слиток', 'слиток'), (3, 'Книга', 'книга'), (4, 'Стигма', 'стигма');
    INSERT INTO recipe (id, name, name_key, product, count, profession, level) VALUES (10, 'Меч', 'меч', 1, 1, 'weaponsmith', 120);
    INSERT INTO recipe_part (recipe_id, ord, item_id, count) VALUES (10, 0, 2, 3);
    INSERT INTO vendor_item (npc_id, item_id, kind) VALUES ('300', 2, 'trade_info');
    INSERT INTO skill (id, internal_name, name, name_key, description, icon, stigma) VALUES
      (5, 'P_Boost', 'Укрепление I', 'укрепление i', 'Больше защиты.', 'skills/p_boost', 0), (6, 'Stigma_Heal', 'Свет', 'свет', NULL, NULL, 1);
    INSERT INTO skill_book (item_id, skill, skill_id, classes) VALUES (3, 'p_boost', 5, '{"fighter": 5}');
    INSERT INTO stigma (item_id, skill, skill_id, gain_level) VALUES (4, 'Stigma_Heal', 6, 9);
    INSERT INTO title (id, name, name_key, race, stats) VALUES (1, 'Хранитель', 'хранитель', 'pc_light', '{"bonus":["maxHp 20"]}');
  `);
  db.prepare("UPDATE item SET dropped_by = ? WHERE id = 2").run(pack([100, 200]));
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("the database card's sources", () => {
  it("name the NPCs that drop an item, the recipes that make it and need it, and who sells it", async () => {
    const all = sample();
    const bar = await itemSources(all, 2);
    expect(bar.drops.map((n) => n.name)).toEqual(["Волк", "Кабан"]);
    expect(bar.dropTotal).toBe(2);
    expect(bar.usedIn).toBe(1);
    expect(bar.vendors).toEqual([{ id: "300", name: "Торговец", kind: "trade_info" }]);
    const sword = await itemSources(all, 1);
    expect(sword.recipes.map((r) => r.name)).toEqual(["Меч"]);
    expect(sword.dropTotal).toBe(0);
  });

  it("give the skill a book teaches and a stigma gives", async () => {
    const all = sample();
    expect(await itemSkill(all, 3)).toEqual({ kind: "book", name: "Укрепление I", description: "Больше защиты.", icon: "skills/p_boost",
      level: null, classes: { fighter: 5 } });
    expect(await itemSkill(all, 4)).toMatchObject({ kind: "stigma", name: "Свет", level: 9 });
    expect(await itemSkill(all, 1)).toBeNull();
  });

  it("read a title as a card; an unknown entity gives nothing", async () => {
    const all = sample();
    expect(await entityCard(all, "title", 1)).toMatchObject({ name: "Хранитель", race: "pc_light" });
    expect(await entityCard(all, "nope", 1)).toBeNull();
  });
});
