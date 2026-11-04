import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import { areas, detail, search } from "./bestiary";
import type { All } from "./npcPoints";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");

/** A small pulse.db in memory with the real schema: three listed NPCs, a technical one, a map marker. */
function sample(): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  db.exec(`
    INSERT INTO npc (id, name, name_key, kind, rank, level, race, faction, role, icon, source, listed, category, title, description,
                     search_text, sort_key, zone_names, hp_bar, has_profile, service, point_count, drop_count, profile) VALUES
      ('100', 'Лесной руфиллин', 'лесной руфиллин', 'Монстр', 'Обычный', 49, 'Зверь', 'Другие', '', 'npc/m.jpg', 'bestiary', 1, 'monster',
       NULL, NULL, 'лесной руфиллин 100', 'лесной руфиллин', 'Брустхонин', 1, 1, 0, 2, 1, '{"stats":{"Макс. ХП":"11578"},"kb_status":"loaded"}'),
      ('200', 'Ёлка-торговец', 'елка-торговец', 'Торговец', 'Обычный', 55, 'Эльф', 'Элийцы', 'merchant', 'npc/t.jpg', 'bestiary', 1, 'npc',
       'Лавка', 'Продаёт предметы.', 'ёлка-торговец 200', 'елка-торговец', 'Сарфан', 1, 1, 0, 0, 0, '{"trade_tabs":[]}'),
      ('300', 'Аргус', 'аргус', 'Монстр', 'Легендарный', 30, 'Дракан', 'Балауры', '', '', 'bestiary', 1, 'monster',
       NULL, NULL, 'аргус 300', 'аргус', '', 4, 0, 0, 0, 0, '{}'),
      ('400', 'Служебный', 'служебный', NULL, NULL, NULL, NULL, NULL, '', '', 'bestiary', 1, 'npc',
       NULL, NULL, 'служебный 400', 'служебный', '', NULL, 0, 1, 0, 0, '{}'),
      ('poi:Аргус', 'Аргус', 'аргус', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'map', 0, NULL, NULL, NULL, 'аргус poi:Аргус', 'аргус', '', NULL, 0, 0, 1, 0, NULL);
    INSERT INTO item (id, name, name_key, grade, icon, drop_icon, dropped_by)
      VALUES (1, 'Сверкающие когти', 'сверкающие когти', 'common', 'icon_item_claw', 'icon_item_claw.png', X'64'); -- dropped by NPC 100
    UPDATE npc SET drops = X'01' WHERE id = '100'; -- drops item 1
    INSERT INTO npc_stock VALUES ('200', 0, '9', 'Зелье жизни', 'зелье жизни', 'common', '1', 'client/potion.png', 'Бакалея', 'Покупка');
    INSERT INTO npc_zone VALUES ('100', '220050000', 'Брустхонин');
    INSERT INTO npc_area VALUES ('100', '220050000', 'a1', 2, 650, 1690, '["Броунир"]', '[[1,2],[3,4]]');
    INSERT INTO npc_alias VALUES ('poi:Аргус', '300');
    INSERT INTO npc_point (npc_id, map_id, x, y, z, source) VALUES
      ('100', '220050000', 653.2, 1692.4, 10, 'map'), ('100', '220050000', 1000, 1000, 1, 'bestiary'), ('poi:Аргус', '210050000', 5, 6, 0, 'map');
  `);
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("the bestiary from pulse.db", () => {
  it("lists only the bestiary's records, not technical ones or the map's markers, by level from the highest", async () => {
    const [rows, total] = await search(sample(), { order: "level_desc" });
    expect(total).toBe(3);
    expect(rows.map((r) => r.id)).toEqual(["200", "100", "300"]);
    expect(rows[1]).toMatchObject({ name: "Лесной руфиллин", level: 49, icon_asset: "npc/m.jpg", point_count: 2, sold: "", dropped: "" });
  });

  it("filters by class, level and finds by name (any case, «ё» as «е»), by a sold or a dropped item", async () => {
    const all = sample();
    expect((await search(all, { rank: "Легендарный" }))[0].map((r) => r.id)).toEqual(["300"]);
    expect((await search(all, { min_level: 40, max_level: 50 }))[0].map((r) => r.id)).toEqual(["100"]);
    expect((await search(all, { text: "ЕЛКА" }))[0].map((r) => r.id)).toEqual(["200"]);
    const [sold] = await search(all, { text: "зелье" });
    expect(sold.map((r) => [r.id, r.sold])).toEqual([["200", "Зелье жизни"]]);
    const [dropped] = await search(all, { text: "когти" });
    expect(dropped.map((r) => [r.id, r.dropped])).toEqual([["100", "Сверкающие когти"]]);
    expect((await search(all, { category: "service" }))[0].map((r) => r.id)).toEqual(["400"]);
  });

  it("gives the card as before: its fields, the profile, goods, drops and the one table's points", async () => {
    const all = sample();
    const card = await detail(all, "100");
    expect(card).toMatchObject({ id: "100", name: "Лесной руфиллин", rank: "Обычный", level: 49, hp_bar: 1, category: "monster",
      icon_asset: "npc/m.jpg", stats: { "Макс. ХП": "11578" }, kb_status: "loaded", stock: [] });
    expect(card!.drops).toEqual([{ item_id: "1", name: "Сверкающие когти", rarity: "common", icon: "icon_item_claw.png", catalog_icon: "icon_item_claw" }]);
    expect(card!.points.map((p: any) => [p.map_id, p.gx, p.gy, p.source])).toEqual([["220050000", 653.2, 1692.4, "map"], ["220050000", 1000, 1000, "bestiary"]]);
    const shop = await detail(all, "200");
    expect(shop!.stock).toEqual([{ item_id: "9", name: "Зелье жизни", rarity: "common", level: "1", icon_asset: "client/potion.png", group: "Бакалея", trade_mode: "Покупка" }]);
    expect((await detail(all, "300"))!.points.map((p: any) => p.map_id)).toEqual(["210050000"]); // the map's marker of its name
    expect(await detail(all, "nobody")).toBeNull();
  });

  it("gives the approximate areas of an NPC", async () => {
    expect(await areas(sample(), "100")).toEqual([{ map_id: "220050000", area_id: "a1", point_count: 2, center: [650, 1690], names: ["Броунир"], polygon: [[1, 2], [3, 4]] }]);
  });
});
