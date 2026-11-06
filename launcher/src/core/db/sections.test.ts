import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import type { All } from "./npcPoints";
import { sectionCounts } from "./sections";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");

function sample(): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  db.exec(`
    INSERT INTO item (id, name, name_key, category) VALUES
      (1, 'Меч', 'меч', 'Оружие'), (2, 'Лук', 'лук', 'Оружие'),
      (3, 'Роба', 'роба', 'Ткань'), (4, 'Куртка', 'куртка', 'Кожа'), (5, 'Кольчуга', 'кольчуга', 'Кольчуга'), (6, 'Латы', 'латы', 'Лата'),
      (7, 'Щит', 'щит', 'Щиты'), (8, 'Кольцо', 'кольцо', 'Украшения'), (9, 'Кость', 'кость', NULL);
    INSERT INTO quest (id, name, name_key) VALUES (1, 'А', 'а'), (2, 'Б', 'б');
    INSERT INTO recipe (id, name, name_key) VALUES (1, 'Р', 'р');
  `);
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("the database menu's counts", () => {
  it("count every item, the weapons, the armour of four kinds, the jewellery, the quests and the recipes", async () => {
    expect(await sectionCounts(sample())).toEqual({
      "db:Предметы": 9, "db:Оружие": 2, "db:Броня": 4, "db:Украшения": 1, "db:Задания": 2, "db:Рецепты": 1,
    });
  });
});
