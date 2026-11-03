/**
 * The NPCs' points from pulse.db, the one game database (docs/ADR-002-pulse-db.md): the map and the bestiary read the
 * same table, so an NPC has the same places in both. Pure: the caller passes `all`, a reading query of the database
 * (the program's db_query, or sql.js on the dev page).
 *
 *   spawnIndex(all)        the map's whole index in the shape of data/maps/spawns.json (core/map/spawns.ts reads it)
 *   pointsOf(all, npcId)   one NPC's points, also those of the map's marker of its name («poi:Имя», npc_alias)
 */

/** data/maps/spawns.json's shape: what core/map/spawns.ts parses. */
export interface SpawnFile {
  names: Record<string, string>;
  zones: Record<string, [string, number, number, number][]>;
  sp_only: string[];
  deco: string[];
}

export type All = (sql: string, params?: unknown[]) => Promise<Record<string, any>[]>;

export interface NpcPoint { map_id: string; x: number; y: number; z: number; source: string }

export async function spawnIndex(all: All): Promise<SpawnFile> {
  const [npcs, points] = await Promise.all([
    all("SELECT id, name, deco, sp_only FROM npc WHERE id IN (SELECT DISTINCT npc_id FROM npc_point) ORDER BY id"),
    all("SELECT npc_id, map_id, x, y, z FROM npc_point ORDER BY rowid"),
  ]);
  const names: Record<string, string> = {};
  const deco: string[] = [];
  const spOnly: string[] = [];
  for (const npc of npcs) {
    names[npc.id] = npc.name;
    if (npc.deco) deco.push(npc.id);
    if (npc.sp_only) spOnly.push(npc.id);
  }
  const zones: SpawnFile["zones"] = {};
  for (const p of points) (zones[p.map_id] ??= []).push([p.npc_id, p.x, p.y, p.z]);
  return { names, zones, sp_only: spOnly, deco };
}

export async function pointsOf(all: All, npcId: string): Promise<NpcPoint[]> {
  const rows = await all(
    "SELECT map_id, x, y, z, source FROM npc_point WHERE npc_id = ?1 OR npc_id IN (SELECT alias FROM npc_alias WHERE npc_id = ?1) ORDER BY rowid",
    [npcId],
  );
  return rows.map((r) => ({ map_id: String(r.map_id), x: Number(r.x), y: Number(r.y), z: Number(r.z), source: String(r.source) }));
}
