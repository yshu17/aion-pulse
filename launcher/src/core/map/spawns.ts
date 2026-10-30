/**
 * Where NPCs and monsters stand: data/maps/spawns.json (tools/import_missing_maps.py) — the client's spawn points of
 * every zone the map has a picture for, by NPC id. Pure: the caller passes the file's text.
 *
 * The map draws none of them by itself (tens of thousands): a search finds an NPC by name, then only its points in
 * the chosen zone are shown.
 */

import { normalize } from "../chat/matcher";
import { pyHypot } from "../py";

export type SpawnPoint = [number, number, number]; // game x, game y, game z

export interface SpawnFound {
  npc: string;
  name: string;
  zones: { map_id: string; count: number }[]; // most points first
  total: number;
}

export class Spawns {
  private byNpc = new Map<string, Map<string, SpawnPoint[]>>();
  private search_: { npc: string; text: string }[] = [];

  constructor(public names: Record<string, string>, zones: Record<string, [string, number, number, number][]>) {
    for (const [mapId, points] of Object.entries(zones)) {
      for (const [npc, x, y, z] of points) {
        let at = this.byNpc.get(npc);
        if (!at) this.byNpc.set(npc, (at = new Map()));
        let list = at.get(mapId);
        if (!list) at.set(mapId, (list = []));
        list.push([x, y, z]);
      }
    }
    this.search_ = [...this.byNpc.keys()].map((npc) => ({ npc, text: normalize(names[npc] ?? "") }));
  }

  /** The text of spawns.json; missing or broken gives an empty index. */
  static parse(text: string | null): Spawns {
    try {
      const data = text ? JSON.parse(text) : null;
      return new Spawns(data?.names ?? {}, data?.zones ?? {});
    } catch {
      return new Spawns({}, {});
    }
  }

  get size(): number {
    return this.byNpc.size;
  }

  /**
   * NPCs whose name holds every word of the query, at most `limit`: whole-name matches first, then names that start
   * with the query, then the rest by name. NPCs of one name with several ids stay apart (they are other NPCs).
   */
  find(query: string, limit = 20): SpawnFound[] {
    const q = normalize(query.trim());
    const words = q.split(/\s+/).filter(Boolean);
    if (!words.length || q.length < 2) return [];
    const hits = this.search_.filter((s) => s.text && words.every((w) => s.text.includes(w)));
    const rank = (s: { text: string }) => (s.text === q ? 0 : s.text.startsWith(q) ? 1 : 2);
    hits.sort((a, b) => rank(a) - rank(b) || a.text.localeCompare(b.text, "ru") || a.npc.localeCompare(b.npc));
    return hits.slice(0, limit).map(({ npc }) => {
      const zones = [...this.byNpc.get(npc)!].map(([map_id, points]) => ({ map_id, count: points.length }))
        .sort((a, b) => b.count - a.count || a.map_id.localeCompare(b.map_id));
      return { npc, name: this.names[npc], zones, total: zones.reduce((sum, z) => sum + z.count, 0) };
    });
  }

  /** The points of an NPC in a zone. */
  points(npc: string, mapId: string): SpawnPoint[] {
    return this.byNpc.get(npc)?.get(mapId) ?? [];
  }

  /** Is there an NPC of this id with a point in this zone? */
  has(npc: string, mapId: string): boolean {
    return this.points(npc, mapId).length > 0;
  }
}

/** The point of a list nearest to a game position. */
export function nearestPoint(points: SpawnPoint[], gx: number, gy: number): SpawnPoint | null {
  let best: SpawnPoint | null = null;
  let metres = Infinity;
  for (const p of points) {
    const d = pyHypot(p[0] - gx, p[1] - gy);
    if (d < metres) { best = p; metres = d; }
  }
  return best;
}
