/**
 * Points of interest for the map tab (data/maps/poi.json, made by tools/build_poi.py) — the port of core/map/poi.py.
 *
 * Pure data: loading (`PoiStore.load(text)`, null = missing file), filtering by layer type, text search, the nearest
 * point of a type with the distance in metres (game units), and clustering of close points for drawing.
 */

import { normalize } from "../chat/matcher";
import { pyHypot, pySplit, pySum } from "../py";

export interface Poi {
  zone: string; // map id, e.g. "220070000"
  type: string; // layer type, e.g. "teleport"
  x: number; // map image pixels
  y: number;
  gx: number; // game coordinates (1 unit ≈ 1 m)
  gy: number;
  name: string;
  note: string; // extra line for the card, e.g. the quests an NPC gives
  side: string; // "dark" / "light": shown only for that side (fortress NPCs, quest givers); "" = always
  layer: number | null; // optional client map layer (Abyss)
}

export type TypeInfo = { group?: string; name?: string; icon?: string; [key: string]: unknown };
export type Transform = (gx: number, gy: number) => [number, number];

class BadFile extends Error {}

const isDict = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

/** Python iteration of a JSON value: lists give items, strings characters, objects keys; anything else fails. */
function items(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (typeof value === "string") return [...value];
  if (isDict(value)) return Object.keys(value);
  throw new BadFile("not iterable");
}

/** Python dict(value) of a JSON value: an object, or a list of key–value pairs. */
function pyDict(value: unknown): Record<string, TypeInfo> {
  if (isDict(value)) return { ...(value as Record<string, TypeInfo>) };
  const out: Record<string, TypeInfo> = {};
  for (const pair of items(value)) {
    const kv = items(pair);
    if (kv.length !== 2 || isDict(kv[0]) || Array.isArray(kv[0])) throw new BadFile("not a pair");
    out[String(kv[0])] = kv[1] as TypeInfo;
  }
  return out;
}

function need(p: Record<string, unknown>, key: string): unknown {
  if (!(key in p)) throw new BadFile(`KeyError: ${key}`);
  return p[key];
}

/** Python dict.get(): a key holding null gives null, not the fallback. */
function get(p: Record<string, unknown>, key: string, fallback: unknown): unknown {
  return key in p ? p[key] : fallback;
}

export class PoiStore {
  constructor(public types: Record<string, TypeInfo>, private zones: Record<string, Poi[]>) {}

  /** Missing or broken file gives an empty store (the map works without layers). */
  static load(text: string | null): PoiStore {
    try {
      if (text === null) throw new BadFile("missing");
      const data = JSON.parse(text);
      if (!isDict(data)) throw new BadFile("not an object");
      const raw = data.zones ?? {};
      if (!isDict(raw)) throw new BadFile("zones is not an object");
      const zones: Record<string, Poi[]> = {};
      for (const [zone, points] of Object.entries(raw)) {
        zones[zone] = items(points).map((p) => {
          if (!isDict(p)) throw new BadFile("point is not an object");
          return {
            zone, type: need(p, "t"), x: need(p, "x"), y: need(p, "y"), gx: need(p, "gx"), gy: need(p, "gy"),
            name: get(p, "name", ""), note: get(p, "note", ""), side: get(p, "side", ""), layer: get(p, "layer", null),
          } as Poi;
        });
      }
      return new PoiStore(pyDict(data.types ?? {}), zones);
    } catch (error) {
      if (error instanceof BadFile || error instanceof SyntaxError) return new PoiStore({}, {});
      throw error;
    }
  }

  /**
   * Map pixels recomputed from game coordinates with each zone's transform (map id -> f(gx, gy)).
   * So the points follow whatever map image a zone uses; zones without a transform keep theirs.
   */
  projected(toImage: Record<string, Transform>): PoiStore {
    const zones: Record<string, Poi[]> = {};
    for (const [zone, points] of Object.entries(this.zones)) {
      const f = toImage[zone];
      zones[zone] = f ? points.map((p) => {
        const [x, y] = f(p.gx, p.gy);
        return { ...p, x, y };
      }) : points;
    }
    return new PoiStore(this.types, zones);
  }

  /** The points of one zone as loaded. */
  zone(zone: string): Poi[] {
    return this.zones[zone] ?? [];
  }

  zoneIds(): string[] {
    return Object.keys(this.zones);
  }

  typeName(type: string): string {
    return (info(this.types[type] ?? {}).name ?? type) as string;
  }

  /** group -> types, both in file order. */
  groups(): Record<string, string[]> {
    const out: Record<string, string[]> = {};
    for (const [type, value] of Object.entries(this.types)) {
      const group = (info(value).group ?? "other") as string;
      (out[group] ??= []).push(type);
    }
    return out;
  }

  /** Points of the given types; with a side, points of the other side are left out. */
  inZone(zone: string, types: Set<string>, side = "", layer: number | null = null): Poi[] {
    return this.zone(zone).filter((p) => types.has(p.type)
      && (!side || !p.side || p.side === side)
      && (layer === null || p.layer === null || p.layer === layer));
  }

  counts(zone: string): Record<string, number> {
    const out: Record<string, number> = {};
    for (const p of this.zone(zone)) out[p.type] = (out[p.type] ?? 0) + 1;
    return out;
  }

  /** Points of the shown layers whose name or type name holds every word of the query. */
  search(zone: string, query: string, types: Set<string>, side = "", layer: number | null = null): Poi[] {
    const words = pySplit(normalize(query));
    if (!words.length) return [];
    return this.inZone(zone, types, side, layer).filter((p) => {
      const text = normalize(`${p.name} ${this.typeName(p.type)}`);
      return words.every((w) => text.includes(w));
    });
  }

  /** Closest point of a type and the distance in metres, null if the zone has none. */
  nearest(zone: string, gx: number, gy: number, type: string): [Poi, number] | null {
    let best: [Poi, number] | null = null;
    for (const p of this.inZone(zone, new Set([type]))) {
      const metres = pyHypot(p.gx - gx, p.gy - gy);
      if (best === null || metres < best[1]) best = [p, metres];
    }
    return best;
  }
}

/** A type entry must be an object, as Python's .get() needs. */
function info(value: unknown): TypeInfo {
  if (!isDict(value)) throw new TypeError("type info is not an object");
  return value as TypeInfo;
}

/**
 * Group points with the same key (default: the type) that fall into one cell of radiusPx.
 * Returns [screen x, screen y, members]; the position is the members' mean on screen.
 *
 * The cells are laid out from the map's own origin (where toScreen puts image point 0, 0), not from the corner of the
 * screen. Dragging the map moves every point and the origin alike, so the same points share a cell however the map
 * is panned: no icon merges or splits, counts do not appear and vanish, and the mean does not jump.
 */
export function cluster(points: Iterable<Poi>, toScreen: Transform, radiusPx: number,
                        key: (p: Poi) => string = (p) => p.type): [number, number, Poi[]][] {
  const [originX, originY] = toScreen(0.0, 0.0);
  const cells = new Map<string, [number, number, Poi][]>();
  for (const p of points) {
    const [sx, sy] = toScreen(p.x, p.y);
    const cell = `${key(p)}\u0000${Math.floor((sx - originX) / radiusPx)}\u0000${Math.floor((sy - originY) / radiusPx)}`;
    let members = cells.get(cell);
    if (members === undefined) cells.set(cell, (members = []));
    members.push([sx, sy, p]);
  }
  return [...cells.values()].map((members) => [
    pySum(members.map((m) => m[0])) / members.length,
    pySum(members.map((m) => m[1])) / members.length,
    members.map((m) => m[2]),
  ]);
}
