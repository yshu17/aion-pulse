import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import type { All } from "./npcPoints";
import { sectionCounts, sectionGrades, sectionKinds, sectionPage } from "./sections";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");

function sample(withSections: boolean): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  db.exec(`
    INSERT INTO item (id, name, name_key, level, category, grade, kind, icon) VALUES
      (1, 'Меч', 'меч', 50, 'Оружие', 'epic', 'Меч', 'icon_item_sword'), (2, 'Лук', 'лук', 30, 'Оружие', 'rare', 'Лук', NULL),
      (3, 'Роба', 'роба', 10, 'Ткань', NULL, NULL, NULL), (4, 'Куртка', 'куртка', 10, 'Кожа', NULL, NULL, NULL),
      (5, 'Кольчуга', 'кольчуга', 10, 'Кольчуга', NULL, NULL, NULL), (6, 'Латы', 'латы', 10, 'Лата', NULL, NULL, NULL),
      (7, 'Щит', 'щит', 10, 'Щиты', NULL, NULL, NULL), (8, 'Кольцо', 'кольцо', NULL, 'Украшения', NULL, NULL, NULL),
      (9, 'Кость', 'кость', NULL, NULL, NULL, NULL, NULL);
    INSERT INTO quest (id, name, name_key, min_level, category) VALUES (1, 'А', 'а', 5, 'quest'), (2, 'Б', 'б', 1, 'quest');
    INSERT INTO recipe (id, name, name_key, product, profession, level) VALUES (1, 'Р', 'р', 1, 'weaponsmith', 100);
    INSERT INTO title (id, name, name_key) VALUES (1, 'Хранитель Фоэты', 'хранитель фоэты');
    INSERT INTO item (id, name, name_key, level, category) VALUES (20, 'Удар I', 'удар i', 10, 'Умения'), (21, 'Удар II', 'удар ii', 20, 'Умения'),
      (22, 'Рывок I', 'рывок i', 5, 'Умения'), (23, 'Пламя I', 'пламя i', 5, 'Умения'), (30, 'Стигма', 'стигма', 20, 'Стигма');
    INSERT INTO skill_book (item_id, skill, classes) VALUES (20, 'FI_Hit_G1', '{"fighter": 10}'), (21, 'FI_Hit_G2', '{"fighter": 20}'),
      (22, 'WA_Dash_G1', '{"warrior": 5}'), (23, 'WI_Flame_G1', '{"wizard": 5}');
    INSERT INTO stigma (item_id, skill, gain_level) VALUES (30, 'KN_Guard_G1', 1);
    INSERT INTO gear_item (id, name, name_key, slot, grp, basic, bonus, enchant) VALUES (4, 'Куртка', 'куртка', 'pants', 'lt_pants', '{}', '[]', 1);
    INSERT INTO pet (id, internal_name, name, name_key, functions) VALUES (1, 'a', 'Боец', 'боец', '["doping", "looting"]'),
      (2, 'b', 'Сумка', 'сумка', '["warehouse"]'), (3, 'c', 'Друг', 'друг', NULL);
  `);
  if (withSections) {
    db.exec(`
      INSERT INTO db_section (key, title, ord, entity, rule, count) VALUES
        ('items', 'Предметы', 0, 'item', 'all', 9), ('weapons', 'Оружие', 1, 'item', 'Оружие', 2),
        ('titles', 'Титулы', 6, 'title', 'all', 1), ('armour', 'Броня', 2, 'item', 'x', 2), ('skill_books', 'Книги умений', 4, 'item', 'x', 4),
        ('stigmas', 'Стигмы', 5, 'item', 'x', 1), ('pets', 'Питомцы', 7, 'pet', 'all', 3), ('quests', 'Задания', 8, 'quest', 'all', 2), ('recipes', 'Рецепты', 9, 'recipe', 'all', 1);
      INSERT INTO db_section_entry (section, entity_id) VALUES
        ('items', 1), ('items', 2), ('items', 3), ('items', 4), ('items', 5), ('items', 6), ('items', 7), ('items', 8), ('items', 9),
        ('weapons', 1), ('weapons', 2), ('armour', 3), ('armour', 4), ('skill_books', 20), ('skill_books', 21), ('skill_books', 22), ('skill_books', 23),
        ('stigmas', 30), ('pets', 1), ('pets', 2), ('pets', 3), ('titles', 1), ('quests', 1), ('quests', 2), ('recipes', 1);
    `);
  }
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("the database menu's counts", () => {
  it("read the sections' sizes the build wrote", async () => {
    expect(await sectionCounts(sample(true))).toEqual({
      "db:Предметы": 9, "db:Оружие": 2, "db:Броня": 2, "db:Книги умений": 4, "db:Стигмы": 1, "db:Титулы": 1, "db:Питомцы": 3, "db:Задания": 2, "db:Рецепты": 1,
    });
  });

  it("count the six older sections of a database without the section tables", async () => {
    expect(await sectionCounts(sample(false))).toEqual({
      "db:Предметы": 14, "db:Оружие": 2, "db:Броня": 4, "db:Украшения": 1, "db:Задания": 2, "db:Рецепты": 1,
    });
  });
});

describe("a page of a section", () => {
  it("lists the section's items with id, name, type, level, grade and picture, sorted and searched", async () => {
    const all = sample(true);
    const page = await sectionPage(all, "weapons", { sort: "level", desc: true });
    expect(page.total).toBe(2);
    expect(page.rows[0]).toEqual({ id: 1, name: "Меч", kind: "Меч", level: 50, grade: "epic", icon: "icon_item_sword" });
    expect(page.rows.map((r) => r.id)).toEqual([1, 2]);
    expect((await sectionPage(all, "weapons", { query: "ЛУК" })).rows.map((r) => r.id)).toEqual([2]); // case folded
    expect((await sectionPage(all, "items", { query: "8" })).rows.map((r) => r.name)).toEqual(["Кольцо"]); // by id
    expect((await sectionPage(all, "items", { limit: 3, offset: 3, sort: "id" })).rows.map((r) => r.id)).toEqual([4, 5, 6]);
  });

  it("lists titles, quests and recipes by their own columns", async () => {
    const all = sample(true);
    expect((await sectionPage(all, "titles")).rows[0]).toEqual({ id: 1, name: "Хранитель Фоэты", kind: "", level: null, grade: "", icon: "" });
    expect((await sectionPage(all, "quests", { sort: "level" })).rows.map((r) => r.level)).toEqual([1, 5]);
    expect((await sectionPage(all, "recipes")).rows[0]).toMatchObject({ kind: "weaponsmith", level: 100, grade: "epic", icon: "icon_item_sword" });
    expect(await sectionPage(all, "no-such")).toEqual({ total: 0, rows: [] });
  });
});

describe("the filters of a section", () => {
  it("filter by grade, type and level range, and list the types under the other filters", async () => {
    const all = sample(true);
    expect((await sectionPage(all, "weapons", { grade: "epic" })).rows.map((r) => r.id)).toEqual([1]);
    expect((await sectionPage(all, "items", { kind: "Лук" })).rows.map((r) => r.id)).toEqual([2]);
    expect((await sectionPage(all, "items", { levelMin: 11, levelMax: 40 })).rows.map((r) => r.id)).toEqual([2]);
    expect(await sectionKinds(all, "weapons")).toEqual([["Лук", 1], ["Меч", 1]]);
    expect(await sectionKinds(all, "weapons", { grade: "rare" })).toEqual([["Лук", 1]]);
    expect(await sectionKinds(all, "titles")).toEqual([]); // titles have no type
  });

  it("lists only the grades that have rows, filters armour by slot, skills by class and by the highest level, pets by what they do", async () => {
    const all = sample(true);
    expect((await sectionGrades(all, "weapons")).sort()).toEqual([["epic", 1], ["rare", 1]]);
    expect(await sectionGrades(all, "weapons", { grade: "epic", kind: "Лук" })).toEqual([["rare", 1]]); // its own filter is left out
    expect((await sectionPage(all, "armour", { slot: "pants" })).rows.map((r) => r.id)).toEqual([4]);
    expect(await sectionKinds(all, "armour")).toEqual([["Кожа", 1], ["Ткань", 1]]); // the type of an armour is its category: the item has no kind of its own
    expect((await sectionPage(all, "skill_books", { cls: "fighter" })).rows.map((r) => r.id).sort()).toEqual([20, 21, 22]); // its own and the warrior's
    expect((await sectionPage(all, "skill_books", { cls: "wizard" })).rows.map((r) => r.id)).toEqual([23]);
    expect((await sectionPage(all, "skill_books", { best: true })).rows.map((r) => r.id).sort()).toEqual([21, 22, 23]); // «… II» wins over «… I»
    expect((await sectionPage(all, "stigmas", { cls: "knight" })).rows.map((r) => r.id)).toEqual([30]);
    expect(await sectionKinds(all, "pets")).toEqual([["Боевой", 1], ["Остальные", 1], ["Склад", 1]]);
    expect((await sectionPage(all, "pets", { kind: "Склад" })).rows.map((r) => r.id)).toEqual([2]);
  });

  it("hide what is above a level but keep the rows that have no level (titles, pets, items without one)", async () => {
    const all = sample(true);
    expect((await sectionPage(all, "items", { hideAbove: 40 })).rows.map((r) => r.id).sort()).toEqual([2, 3, 4, 5, 6, 7, 8, 9]);
    expect((await sectionPage(all, "titles", { hideAbove: 55 })).total).toBe(1);
  });
});
