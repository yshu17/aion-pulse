/**
 * The links of a map point to the program's cards (docs/TASKS_TG_2026-11-18.md, tasks 15 and 17): the quests named in the
 * point's note open in «База данных → Задания», the point's NPC opens in «NPC» (a merchant on its goods). Reading only.
 *
 *   questNote(note) -> { head, names, more } | null
 *       the quests of a note «Задания (2): A; B» (data/maps/poi.json): head «Задания (2): », the names, and `more` when the
 *       list ends with «…» (the note was cut); null for a note without quests
 *   poiLinks(all, name, mapId, questNames) -> { npc, quests }
 *       npc     { id, name, sells } of the NPC tab's record of that name: one standing in the zone mapId first, then the one
 *               with the most points; null when the tab has none
 *       quests  quest name -> quest id (strings); a name used by several quests takes the one this NPC gives, else the
 *               lowest id; a name not in the database is left out
 */

import type { All } from "./npcPoints";

export interface QuestNote { head: string; names: string[]; more: boolean }
export interface PoiNpc { id: string; name: string; sells: boolean }
export interface PoiLinks { npc: PoiNpc | null; quests: Record<string, string> }

export function questNote(note: string): QuestNote | null {
  const found = /^(.*?\(\d+\): )(.+)$/.exec(note);
  if (!found) return null;
  const parts = found[2].split("; ").map((s) => s.trim()).filter(Boolean);
  const more = parts[parts.length - 1] === "…";
  return { head: found[1], names: more ? parts.slice(0, -1) : parts, more };
}

export async function poiLinks(all: All, name: string, mapId: string, questNames: string[]): Promise<PoiLinks> {
  const [row] = await all(
    "SELECT n.id, n.name, EXISTS (SELECT 1 FROM npc_stock s WHERE s.npc_id = n.id) AS sells FROM npc n WHERE n.name = ? AND n.listed = 1 "
      + "ORDER BY EXISTS (SELECT 1 FROM npc_zone z WHERE z.npc_id = n.id AND z.map_id = ?) DESC, n.service, n.point_count DESC, n.id LIMIT 1",
    [name, mapId],
  );
  const npc = row ? { id: String(row.id), name: String(row.name), sells: Boolean(row.sells) } : null;
  const quests: Record<string, string> = {};
  if (questNames.length) {
    const rows = await all(
      "SELECT name, id FROM quest WHERE name IN (SELECT value FROM json_each(?)) ORDER BY name, (giver = ?) DESC, id",
      [JSON.stringify(questNames), npc?.id ?? ""],
    );
    for (const q of rows) quests[q.name] ??= String(q.id);
  }
  return { npc, quests };
}

/** An item by its exact name (a gathering node's resource on the map), the lowest id; null when the database has none. */
export async function itemByName(all: All, name: string): Promise<{ id: string; name: string } | null> {
  const [row] = await all("SELECT id, name FROM item WHERE name = ? ORDER BY id LIMIT 1", [name]);
  return row ? { id: String(row.id), name: String(row.name) } : null;
}
