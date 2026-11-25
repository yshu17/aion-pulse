import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import { bestMap, dropperRows, dropperZones, filterDroppers, itemDroppers, mapPoints, UNKNOWN_ZONE, zoneCounts } from "./itemDroppers";
import type { All } from "./npcPoints";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");
const NAMES = { "310090000": "Крепость Индрата" };

/** dropped_by as core/pulse_db/build.py packs it: steps between sorted ids, 7 bits a byte, the high bit while more follow. */
function pack(ids: number[]): Uint8Array {
  const out: number[] = [];
  let previous = 0;
  for (const id of [...ids].sort((a, b) => a - b)) {
    let v = id - previous;
    previous = id;
    for (;;) { const byte = v % 128; v = Math.floor(v / 128); out.push(v ? byte + 128 : byte); if (!v) break; }
  }
  return Uint8Array.from(out);
}

function sample(): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  db.exec(`
    INSERT INTO npc (id, name, name_key, source, listed, point_count, level, rank, zone_names, service) VALUES
      ('1', 'Наг-маг', 'наг-маг', 'bestiary', 1, 2, 46, 'Элитный', 'Интердика', 0),
      ('2', 'Наг-маг', 'наг-маг', 'bestiary', 1, 1, 47, 'Элитный', 'Интердика', 0),
      ('3', 'Башня', 'башня', 'bestiary', 1, 1, 46, 'Обычный', '', 0),
      ('4', 'Ёж', 'еж', 'bestiary', 1, 0, 40, 'Обычный', '', 0),
      ('5', 'Два_Дома', 'x', 'bestiary', 1, 0, 40, '', '', 0),
      ('6', 'Странник', 'странник', 'bestiary', 1, 0, 50, '', 'Келькмарос, Теобомос', 0);
    INSERT INTO npc_point (npc_id, map_id, x, y, z, source) VALUES
      ('1', '210040000', 1, 2, 3, 'map'), ('1', '210040000', 4, 5, 6, 'map'), ('2', '210040000', 7, 8, 9, 'map'), ('3', '310090000', 1, 1, 1, 'map');
  `);
  db.prepare("INSERT INTO item (id, name, name_key, dropped_by) VALUES (900, 'Серьга', 'серьга', ?)").run(pack([1, 2, 3, 4, 5, 6]));
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("who drops an item", () => {
  it("lists the named NPCs with level, zones and the points on each map; a missing zone comes from the maps of the points", async () => {
    const list = await itemDroppers(sample(), 900, NAMES);
    expect(list.map((n) => n.name)).toEqual(["Башня", "Ёж", "Наг-маг", "Наг-маг", "Странник"]);
    expect(list[0]).toEqual({ id: "3", name: "Башня", level: 46, rank: "Обычный", zones: ["Крепость Индрата"], maps: { "310090000": 1 }, points: 1 });
    expect(dropperZones(list[1])).toEqual([UNKNOWN_ZONE]);
    expect(list[4].zones).toEqual(["Келькмарос", "Теобомос"]);
  });

  it("counts an NPC of two zones in both, unknown places last", async () => {
    const list = await itemDroppers(sample(), 900, NAMES);
    expect(zoneCounts(list)).toEqual([["Интердика", 2], ["Келькмарос", 1], ["Крепость Индрата", 1], ["Теобомос", 1], [UNKNOWN_ZONE, 1]]);
  });

  it("filters by a part of the name or the zone, by a zone and by having points", async () => {
    const list = await itemDroppers(sample(), 900, NAMES);
    expect(filterDroppers(list, { query: "еж" }).map((n) => n.id)).toEqual(["4"]);
    expect(filterDroppers(list, { query: "интердика" }).map((n) => n.id)).toEqual(["1", "2"]);
    expect(filterDroppers(list, { zone: "Теобомос" }).map((n) => n.id)).toEqual(["6"]);
    expect(filterDroppers(list, { onlyMap: true }).map((n) => n.id)).toEqual(["3", "1", "2"]);
  });

  it("puts the same name in one place together and sorts by a column", async () => {
    const list = await itemDroppers(sample(), 900, NAMES);
    const rows = dropperRows(list, true, "level", -1);
    expect(rows.map((r) => [r.name, r.members.length, r.low, r.high, r.points])).toEqual([
      ["Странник", 1, 50, 50, 0], ["Наг-маг", 2, 46, 47, 3], ["Башня", 1, 46, 46, 1], ["Ёж", 1, 40, 40, 0]]);
    expect(dropperRows(list, false, "points", 1).map((r) => r.id)[0]).toBe("1");
  });

  it("picks the map with the most points and reads those points", async () => {
    const all = sample();
    const list = await itemDroppers(all, 900, NAMES);
    expect(bestMap(list)).toEqual({ map_id: "210040000", points: 3, npcs: ["1", "2"], others: 1 });
    expect(bestMap(list.filter((n) => n.id === "4"))).toBeNull();
    expect(await mapPoints(all, ["1", "2"], "210040000")).toEqual([[1, 2, 3], [4, 5, 6], [7, 8, 9]]);
  });
});
