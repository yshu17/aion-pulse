import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import { filterNpcQuests, npcQuests } from "./npcQuests";
import type { All } from "./npcPoints";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");

function sample(): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  db.exec(`
    INSERT INTO npc (id, name, name_key, source, listed, point_count) VALUES
      ('1', 'Вотан', 'вотан', 'bestiary', 1, 1), ('2', 'Энир', 'энир', 'bestiary', 1, 1), ('3', 'Тихий', 'тихий', 'bestiary', 1, 1);
    INSERT INTO quest (id, name, name_key, min_level, category, repeatable, giver, ender) VALUES
      (20, 'Защитники', 'защитники', 46, 'quest | Арэшурат', 1, '2', '1'),
      (10, 'Встреча', 'встреча', 25, 'quest | Арэшурат', 0, '1', NULL),
      (30, 'Туда и обратно', 'туда и обратно', 40, 'event', 0, '1', '1');
  `);
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("an NPC's quests", () => {
  it("lists what it gives and what it takes by level, with the zone and the one who gives a taken quest", async () => {
    expect(await npcQuests(sample(), "1")).toEqual([
      { id: "10", name: "Встреча", level: 25, zone: "Арэшурат", repeat: false, gives: true, takes: false, giver: "" },
      { id: "30", name: "Туда и обратно", level: 40, zone: "", repeat: false, gives: true, takes: false, giver: "" },
      { id: "20", name: "Защитники", level: 46, zone: "Арэшурат", repeat: true, gives: false, takes: true, giver: "Энир" },
    ]);
  });

  it("is empty for an NPC without quests", async () => {
    expect(await npcQuests(sample(), "3")).toEqual([]);
  });

  it("filters by the role and by a part of the name, ignoring case and «ё»", async () => {
    const list = await npcQuests(sample(), "1");
    expect(filterNpcQuests(list, "takes", "").map((q) => q.id)).toEqual(["20"]);
    expect(filterNpcQuests(list, "gives", "").map((q) => q.id)).toEqual(["10", "30"]);
    expect(filterNpcQuests(list, "all", "ВСТРЕЧ").map((q) => q.id)).toEqual(["10"]);
  });
});
