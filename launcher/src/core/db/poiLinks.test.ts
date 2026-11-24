import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import { itemByName, poiLinks, questNote } from "./poiLinks";
import type { All } from "./npcPoints";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");

/**
 * Two NPCs named «Анорамас» (one in zone 210010000, one elsewhere), a merchant «Лана» with goods, a quest name used twice
 * (the one given by the zone's Анорамас must win) and a record the NPC tab does not list.
 */
function sample(): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  db.exec(`
    INSERT INTO npc (id, name, name_key, source, listed, point_count) VALUES
      ('100', 'Анорамас', 'анорамас', 'bestiary', 1, 1), ('101', 'Анорамас', 'анорамас', 'bestiary', 1, 9),
      ('poi:Анорамас', 'Анорамас', 'анорамас', 'map', 0, 1), ('200', 'Лана', 'лана', 'bestiary', 1, 1);
    INSERT INTO npc_zone VALUES ('100', '210010000', 'Пойета'), ('101', '220010000', 'Исхальген');
    INSERT INTO npc_stock (npc_id, ord, item_id, name, name_key) VALUES ('200', 0, '901', 'Хлеб', 'хлеб');
    INSERT INTO quest (id, name, name_key, giver) VALUES
      (10, 'Истребление мют', 'истребление мют', '101'), (11, 'Истребление мют', 'истребление мют', '100'),
      (12, 'Заразная мюта', 'заразная мюта', NULL);
  `);
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("questNote", () => {
  it("splits the quests of a map point's note", () => {
    expect(questNote("Задания (2): Заразная мюта; Истребление мют")).toEqual({ head: "Задания (2): ", names: ["Заразная мюта", "Истребление мют"], more: false });
    expect(questNote("Элийские задания (1): [Атака] Сбор")).toEqual({ head: "Элийские задания (1): ", names: ["[Атака] Сбор"], more: false });
  });

  it("keeps the «…» of a cut list apart", () => {
    expect(questNote("Задания (8): Первое; Второе; …")).toEqual({ head: "Задания (8): ", names: ["Первое", "Второе"], more: true });
  });

  it("is null for a note without quests", () => {
    expect(questNote("Стоит, когда крепостью владеют элийцы.")).toBeNull();
    expect(questNote("")).toBeNull();
  });
});

describe("poiLinks", () => {
  it("finds the NPC of the point, the one standing in the zone first", async () => {
    const links = await poiLinks(sample(), "Анорамас", "210010000", []);
    expect(links.npc).toEqual({ id: "100", name: "Анорамас", sells: false });
  });

  it("takes the NPC with the most points when none stands in the zone", async () => {
    expect((await poiLinks(sample(), "Анорамас", "999", [])).npc?.id).toBe("101");
  });

  it("says when the NPC sells something", async () => {
    expect((await poiLinks(sample(), "Лана", "210010000", [])).npc).toEqual({ id: "200", name: "Лана", sells: true });
  });

  it("names the quests by id, the one the point's NPC gives first; an unknown name has no link", async () => {
    const links = await poiLinks(sample(), "Анорамас", "210010000", ["Заразная мюта", "Истребление мют", "Нет такого"]);
    expect(links.quests).toEqual({ "Заразная мюта": "12", "Истребление мют": "11" });
  });

  it("has no NPC for a name the NPC tab does not list", async () => {
    expect((await poiLinks(sample(), "Нет такого", "210010000", [])).npc).toBeNull();
  });

  it("finds a gathering resource's item by its exact name", async () => {
    const db = new DatabaseSync(":memory:");
    db.exec(SCHEMA);
    db.exec("INSERT INTO item (id, name, name_key) VALUES (6, 'Адамантит', 'адамантит'), (5, 'Адамантит', 'адамантит');");
    const all: All = async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
    expect(await itemByName(all, "Адамантит")).toEqual({ id: "5", name: "Адамантит" });
    expect(await itemByName(all, "Нет")).toBeNull();
  });
});
