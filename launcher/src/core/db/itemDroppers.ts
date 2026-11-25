/**
 * «Добыча» of an item's card as a table: who drops it, where and at what level (docs/TASKS_TG_2026-11-18.md, task 34).
 * Reading only; the map names (data/map_names.tsv) are given by the caller.
 *
 *   itemDroppers(all, itemId, mapNames) -> Dropper[]   the named NPCs of item.dropped_by, by name
 *     zones   npc.zone_names cut at «, »; when empty, the names of the maps its points are on
 *     maps    map_id -> how many points it has there; points = their sum
 *   dropperZones(d) -> its zones, or [UNKNOWN_ZONE]
 *   zoneCounts(list) -> [zone, NPCs][]   the most first (a NPC of two zones in both), the unknown place last
 *   filterDroppers(list, { query?, zone?, onlyMap? }) -> Dropper[]   query: a part of the name or a zone, «ё» as «е»
 *   dropperRows(list, together, key, dir) -> DropperRow[]   one row per name and place when `together`
 *     key: "name" | "level" | "zone" | "points" (the most points first for dir 1); dir 1 or -1
 *   bestMap(list) -> { map_id, points, npcs, others } | null   the map with the most points, who is on it, how many other maps
 *   mapPoints(all, npcIds, mapId) -> [x, y, z][]   game coordinates, as the map takes them
 */
import { unpackIds } from "./packed";
import type { All } from "./npcPoints";

export interface Dropper { id: string; name: string; level: number; rank: string; zones: string[]; maps: Record<string, number>; points: number }
export interface DropperRow { key: string; id: string; name: string; rank: string; zones: string[]; low: number; high: number; points: number; members: Dropper[] }
export type DropSort = "name" | "level" | "zone" | "points";

export const UNKNOWN_ZONE = "Место неизвестно";
// the NPCs a card can name (as core/db/catalogCard.ts): technical records stay out
const NAMED = "name <> '' AND service = 0 AND instr(name, '_') = 0";

export async function itemDroppers(all: All, itemId: number, mapNames: Record<string, string>): Promise<Dropper[]> {
  const [item] = await all("SELECT dropped_by FROM item WHERE id = ?", [itemId]);
  const ids = unpackIds(item?.dropped_by, true).map(String);
  if (!ids.length) return [];
  const json = JSON.stringify(ids);
  const [npcs, points] = await Promise.all([
    all(`SELECT id, name, level, rank, zone_names FROM npc WHERE id IN (SELECT value FROM json_each(?)) AND ${NAMED} ORDER BY level, id`, [json]),
    all("SELECT npc_id, map_id, count(*) AS n FROM npc_point WHERE npc_id IN (SELECT value FROM json_each(?)) GROUP BY npc_id, map_id", [json]),
  ]);
  const maps = new Map<string, Record<string, number>>();
  for (const p of points) {
    const own = maps.get(String(p.npc_id)) ?? {};
    own[String(p.map_id)] = Number(p.n);
    maps.set(String(p.npc_id), own);
  }
  return npcs.sort((a, b) => String(a.name).localeCompare(String(b.name), "ru")).map((n) => { // SQLite would put «Ё» before «А»
    const own = maps.get(String(n.id)) ?? {};
    const written = String(n.zone_names ?? "").split(", ").filter(Boolean);
    const zones = written.length ? written : [...new Set(Object.keys(own).map((m) => mapNames[m]).filter(Boolean))].sort((a, b) => a.localeCompare(b, "ru"));
    return { id: String(n.id), name: String(n.name), level: Number(n.level) || 0, rank: String(n.rank ?? ""), zones, maps: own,
      points: Object.values(own).reduce((sum, v) => sum + v, 0) };
  });
}

export const dropperZones = (d: Pick<Dropper, "zones">): string[] => (d.zones.length ? d.zones : [UNKNOWN_ZONE]);

export function zoneCounts(list: Dropper[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const d of list) for (const z of dropperZones(d)) counts.set(z, (counts.get(z) ?? 0) + 1);
  return [...counts].sort((a, b) => Number(a[0] === UNKNOWN_ZONE) - Number(b[0] === UNKNOWN_ZONE) || b[1] - a[1] || a[0].localeCompare(b[0], "ru"));
}

const fold = (t: string) => t.toLowerCase().split("ё").join("е");

export function filterDroppers(list: Dropper[], f: { query?: string; zone?: string; onlyMap?: boolean }): Dropper[] {
  const q = fold((f.query ?? "").trim());
  return list.filter((d) => (!f.zone || dropperZones(d).includes(f.zone)) && (!f.onlyMap || d.points > 0)
    && (!q || fold(`${d.name} ${d.zones.join(" ")}`).includes(q)));
}

export function dropperRows(list: Dropper[], together: boolean, key: DropSort, dir: 1 | -1): DropperRow[] {
  const groups = new Map<string, Dropper[]>();
  for (const d of list) {
    const id = together ? `${d.name}|${dropperZones(d).join(", ")}` : d.id;
    const group = groups.get(id);
    if (group) group.push(d); else groups.set(id, [d]);
  }
  const rows: DropperRow[] = [...groups].map(([id, members]) => ({
    key: id, id: members[0].id, name: members[0].name,
    rank: members.find((x) => x.rank === "Героический")?.rank ?? members.find((x) => x.rank === "Элитный")?.rank ?? members[0].rank,
    zones: members[0].zones, low: Math.min(...members.map((x) => x.level)), high: Math.max(...members.map((x) => x.level)),
    points: members.reduce((sum, x) => sum + x.points, 0), members,
  }));
  const by = (a: DropperRow, b: DropperRow) =>
    key === "level" ? a.low - b.low || a.high - b.high
      : key === "points" ? b.points - a.points
        : key === "zone" ? dropperZones(a).join().localeCompare(dropperZones(b).join(), "ru")
          : a.name.localeCompare(b.name, "ru");
  return rows.sort((a, b) => by(a, b) * dir || a.name.localeCompare(b.name, "ru"));
}

export function bestMap(list: Dropper[]): { map_id: string; points: number; npcs: string[]; others: number } | null {
  const total = new Map<string, number>();
  for (const d of list) for (const [map, n] of Object.entries(d.maps)) total.set(map, (total.get(map) ?? 0) + n);
  const [best] = [...total].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  if (!best) return null;
  return { map_id: best[0], points: best[1], npcs: list.filter((d) => d.maps[best[0]]).map((d) => d.id), others: total.size - 1 };
}

export async function mapPoints(all: All, npcIds: string[], mapId: string): Promise<[number, number, number][]> {
  const rows = await all(
    "SELECT x, y, z FROM npc_point WHERE map_id = ? AND npc_id IN (SELECT value FROM json_each(?)) ORDER BY npc_id, x, y",
    [mapId, JSON.stringify(npcIds)],
  );
  return rows.map((r) => [Number(r.x), Number(r.y), Number(r.z ?? 0)]);
}
