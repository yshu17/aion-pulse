/**
 * Where NPCs and monsters stand: data/maps/spawns.json (tools/import_missing_maps.py) — the client's spawn points of
 * every zone the map has a picture for, by NPC id. Pure: the caller passes the file's text.
 *
 * `sp_only` lists the NPCs that have no point but the client's SP ones. The map draws none of them by itself (tens of thousands): a search finds an NPC by name, then only its points in
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
  private spOnly_: Set<string>;
  private deco_: Set<string>;
  private decoByZone = new Map<string, { npc: string; x: number; y: number }[]>();

  constructor(
    public names: Record<string, string>,
    private rawZones: Record<string, [string, number, number, number][]>,
    rawSpOnly: string[] = [],
    rawDeco: string[] = [],
  ) {
    this.deco_ = new Set(rawDeco);
    const zones = rawZones;
    this.spOnly_ = new Set(rawSpOnly);
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
      return new Spawns(data?.names ?? {}, data?.zones ?? {}, data?.sp_only ?? [], data?.deco ?? []);
    } catch {
      return new Spawns({}, {});
    }
  }

  /** Every zone an NPC stands in with its points; any id counts, also a pseudo NPC of the map («poi:Name»). Empty for an unknown one. */
  zonesOf(npc: string): { map_id: string; points: SpawnPoint[] }[] {
    return [...(this.byNpc.get(npc) ?? [])].map(([map_id, points]) => ({ map_id, points }));
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

  /**
   * Is this NPC known only by the client's spawn points (SP) and by no static point of the game's data? Such an NPC may
   * appear on a condition (a quest, an event, a script): an SP point alone does not say so, the conditions are not checked.
   */
  spOnly(npc: string): boolean {
    return this.spOnly_.has(npc);
  }

  /**
   * Is this NPC decorative: a named NPC of the general kind with no function (no merchant, teleport, kisk …) that gives and
   * takes no quest. Tools/import_missing_maps.py decides it from the game's data; the game's data has no flag for «can be
   * talked to», so a few talking NPCs may be in it.
   */
  isDeco(npc: string): boolean {
    return this.deco_.has(npc);
  }

  /** Every point of the decorative NPCs of a zone (the small blue dots of the map), with the NPC of each. */
  decoPoints(mapId: string): { npc: string; x: number; y: number }[] {
    let list = this.decoByZone.get(mapId);
    if (!list) {
      list = [];
      for (const [npc, x, y] of this.rawZones[mapId] ?? []) if (this.deco_.has(npc)) list.push({ npc, x, y });
      this.decoByZone.set(mapId, list);
    }
    return list;
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

/** A spawn area of the map: a circle in game coordinates around one or several close spawn points. */
export interface SpawnArea { x: number; y: number; r: number }

/**
 * The blue spawn areas of an NPC: points closer than two radii join one area (chains of them too), so overlapping
 * circles become one; an area is centred on its points and reaches a radius past the farthest one.
 */
export function spawnAreas(points: SpawnPoint[], radius: number): SpawnArea[] {
  const group = points.map((_, i) => i);
  const root = (i: number): number => (group[i] === i ? i : (group[i] = root(group[i])));
  for (let i = 0; i < points.length; i++) {
    for (let j = i + 1; j < points.length; j++) {
      if (Math.hypot(points[i][0] - points[j][0], points[i][1] - points[j][1]) < radius * 2) group[root(i)] = root(j);
    }
  }
  const members = new Map<number, SpawnPoint[]>();
  points.forEach((p, i) => members.set(root(i), [...(members.get(root(i)) ?? []), p]));
  return [...members.values()].map((ps) => {
    const x = ps.reduce((sum, p) => sum + p[0], 0) / ps.length;
    const y = ps.reduce((sum, p) => sum + p[1], 0) / ps.length;
    return { x, y, r: Math.max(...ps.map((p) => Math.hypot(p[0] - x, p[1] - y))) + radius };
  });
}
