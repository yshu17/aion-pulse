import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import { Spawns } from "../map/spawns";
import { pointsOf, spawnIndex, type All } from "./npcPoints";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");

/** A small pulse.db in memory, the real schema, as the program's db_query answers it. */
function sample(): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  db.exec(`
    INSERT INTO npc (id, name, name_key, rank, level, deco, sp_only, source) VALUES
      ('100', 'Лесной руфиллин', 'лесной руфиллин', 'Обычный', 49, 0, 1, 'bestiary'),
      ('300', 'Житель', 'житель', NULL, NULL, 1, 0, 'client'),
      ('799323', 'Теграк', 'теграк', 'Легендарный', 60, 0, 0, 'bestiary'),
      ('poi:Теграк', 'Теграк', 'теграк', NULL, NULL, 0, 0, 'map');
    INSERT INTO npc_alias VALUES ('poi:Теграк', '799323');
    INSERT INTO npc_point (npc_id, map_id, x, y, z, source) VALUES
      ('100', '220050000', 653.2, 1692.4, 10, 'map'), ('100', '220050000', 1000, 1000, 1, 'bestiary'),
      ('300', '220070000', 5, 6, 0, 'map'), ('poi:Теграк', '220070000', 1769.1, 1765.7, 0, 'map');
  `);
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("NPC points from pulse.db", () => {
  it("gives the map its whole index in the shape of spawns.json: names, points by zone, the flags", async () => {
    const data = await spawnIndex(sample());
    expect(data.names).toEqual({ "100": "Лесной руфиллин", "300": "Житель", "poi:Теграк": "Теграк" }); // only NPCs with points
    expect(data.zones["220050000"]).toEqual([["100", 653.2, 1692.4, 10], ["100", 1000, 1000, 1]]);
    expect(data.sp_only).toEqual(["100"]);
    expect(data.deco).toEqual(["300"]);
    const spawns = Spawns.parse(JSON.stringify(data)); // the map's index is built as before
    expect(spawns.points("100", "220050000")).toHaveLength(2);
    expect(spawns.isDeco("300")).toBe(true);
  });

  it("gives an NPC its points, also the ones of the map's marker of its name", async () => {
    const all = sample();
    expect(await pointsOf(all, "799323")).toEqual([{ map_id: "220070000", x: 1769.1, y: 1765.7, z: 0, source: "map" }]);
    expect((await pointsOf(all, "100")).map((p) => p.source)).toEqual(["map", "bestiary"]);
    expect(await pointsOf(all, "nobody")).toEqual([]);
  });
});
