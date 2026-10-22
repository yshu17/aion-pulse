/**
 * Map zones: the zone index, the area names of each zone and the filter groups of the menu — the port of
 * core/map/zones.py. Pure: the caller passes the text of maps.json and labels.tsv and says which picture files exist.
 *
 * A Zone converts game coordinates to picture pixels with `toImage(zone, x, y)`.
 */

import { pyFloat, pyHypot } from "../py";

export { pyFloat };

export const SIDES: Record<string, string> = { dark: "Асмодиане", light: "Элийцы" };
export const LABEL_LEVELS = ["main", "zoom"];

/** The «Метки» menu: group -> [title, point types]. Every group can be switched off; there is no «all» entry. */
export const FILTER_GROUPS: Record<string, [string, string[]]> = {
  buildings: ["Здания", ["fortress", "artifact", "portal", "raid_boss"]],
  dungeons: ["Подземелья", ["dungeon"]],
  rifts: ["Пространственные разломы", ["direct_portal", "tunnel"]],
  merchants: ["Торговцы", ["merchant", "coin_merchant", "vendor"]],
  teleports: ["Телепорты", ["teleport"]],
  services: ["Склад, стигмы, почта", ["warehouse", "stigma", "postbox", "bindstone"]],
  quests: ["Задания", ["quest_give", "quest_important", "quest_event"]],
};
export const CAPITALS = new Set(["110010000", "120010000"]); // Elysium, Pandaemonium
export const SHOWN_TYPES = ["teleport", "bindstone", "warehouse", "merchant", "coin_merchant", "vendor", "stigma",
  "postbox", "fortress", "artifact", "dungeon", "tunnel", "portal", "raid_boss", "direct_portal"];
export const QUEST_TYPES = ["quest_give", "quest_important", "quest_event"];

export interface Place {
  map_id: string;
  x: number; // game coordinates
  y: number;
  label: string;
  note: string; // «12:03 Nick: message» for pins from the chat
}

export type Label = [number, number, string, string]; // image x, image y, text, level

export interface Zone {
  map_id: string;
  name: string;
  file: string; // picture file relative to the maps folder
  size: number;
  kx: [number, number];
  ky: [number, number];
  labels: Label[];
  layers: [number, string, string][]; // Abyss layer id, display name, picture file
  label_layers: (number | null)[]; // the Abyss layer of each label (same order), null: every layer
  side: string; // "dark", "light" or "" for a zone both sides share
}

export function toImage(zone: Zone, x: number, y: number): [number, number] {
  return [zone.kx[0] * y + zone.kx[1], zone.ky[0] * x + zone.ky[1]];
}

function rows(text: string | null): string[][] {
  if (text === null) return [];
  return text.split(/\r\n|\n|\r/).filter((line) => line !== "").map((line) => line.split("\t"))
    .filter((parts) => !parts[0].startsWith("#") && (parts.length === 5 || parts.length === 6)
      && LABEL_LEVELS.includes(parts[1]));
}

/** labels.tsv -> {map id: [[game x, game y, text, level]]}; «|» in a name is a line break. */
export function parseLabels(text: string | null): Record<string, Label[]> {
  const zones: Record<string, Label[]> = {};
  for (const parts of rows(text)) {
    const x = pyFloat(parts[2]);
    const y = pyFloat(parts[3]);
    if (x === null || y === null) continue;
    (zones[parts[0]] ??= []).push([x, y, parts[4].replace(/\|/g, "\n"), parts[1]]);
  }
  return zones;
}

/** The optional 6th column of labels.tsv: the Abyss layer of each label, null where a label has none. */
export function parseLabelLayers(text: string | null): Record<string, (number | null)[]> {
  const zones: Record<string, (number | null)[]> = {};
  for (const parts of rows(text)) {
    if (pyFloat(parts[2]) === null || pyFloat(parts[3]) === null) continue;
    (zones[parts[0]] ??= []).push(parts.length === 6 && /^\d+$/.test(parts[5]) ? parseInt(parts[5], 10) : null);
  }
  return zones;
}

/**
 * maps.json + labels.tsv -> {map id: Zone}. `exists(file)` says whether a picture file is there (a zone without its
 * picture is skipped, as are missing layer pictures). Broken JSON gives {}.
 */
export function parseZones(mapsJson: string | null, labelsText: string | null, names: Record<string, string>,
                           exists: (file: string) => boolean): Record<string, Zone> {
  let index: Record<string, any>;
  try {
    index = mapsJson === null ? {} : JSON.parse(mapsJson);
  } catch {
    return {};
  }
  const labels = parseLabels(labelsText);
  const labelLayers = parseLabelLayers(labelsText);
  const zones: Record<string, Zone> = {};
  for (const [mapId, info] of Object.entries(index)) {
    if (!exists(info.file)) continue;
    const kx: [number, number] = [info.x[0], info.x[1]];
    const ky: [number, number] = [info.y[0], info.y[1]];
    zones[mapId] = {
      map_id: mapId,
      name: names[mapId] ?? mapId,
      file: info.file,
      size: Math.trunc(info.size),
      kx,
      ky,
      labels: (labels[mapId] ?? []).map(([gx, gy, text, level]) => [kx[0] * gy + kx[1], ky[0] * gx + ky[1], text, level]),
      layers: (info.layers ?? []).filter((layer: any) => exists(layer.file))
        .map((layer: any) => [parseInt(String(layer.id), 10), layer.name ?? `Слой ${layer.id}`, layer.file]),
      label_layers: labelLayers[mapId] ?? [],
      side: info.side in SIDES ? info.side : "",
    };
  }
  return zones;
}

/** Merge all selected groups in one zone into a circle [x, y, radius] covering their points; null without points. */
export function enclosingSpawnCircle(polygons: Iterable<Iterable<[unknown, unknown]>>): [number, number, number] | null {
  const float = (v: unknown): number => {
    if (typeof v === "number") return v;
    const parsed = typeof v === "string" ? pyFloat(v) : null;
    if (parsed === null) throw new TypeError(`float(${JSON.stringify(v)})`);
    return parsed;
  };
  const points: [number, number][] = [];
  for (const polygon of polygons) for (const [x, y] of polygon) points.push([float(x), float(y)]);
  if (!points.length) return null;
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const radius = Math.max(24.0, Math.max(...points.map(([x, y]) => pyHypot(x - cx, y - cy))) + 12);
  return [cx, cy, radius];
}
