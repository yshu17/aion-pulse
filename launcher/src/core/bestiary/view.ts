/**
 * What the Bestiary screen shows of the store's rows and cards — pure, no window:
 *
 *   LEVELS / levelRange(label)   the «Уровень» choices and their bounds for BestiaryStore.search
 *   RANK_CHIPS                   the class chips: [label, rank of the database]
 *   rowSubtitle(row)             «Ур. 55 · Торговец · Обычный» under a list row's name
 *   mainPlace(detail) / placeAt(detail, zone)   the zone with the most points / a chosen zone, and the first point there
 *   hpFrame(detail)              the HP artwork of the card (rank-specific part of the sprite)
 *   statGroups(detail) / rankTier(rank)   the card's four key numbers and the other facts / a rank's tier 1…4
 *   iconPath(asset)              a picture's path inside the bestiary's icon folder (data/bestiary/icons)
 *   rarityClass(rarity)          the colour class of an item's name
 *   roleLabel(role)              the NPC's service in Russian (merchant -> «Торговец»)
 */

import { overviewRows, type Detail } from "./card";
import { statText } from "./labels";

export const LEVELS = ["Любой", "1–10", "11–20", "21–30", "31–40", "41–50", "51–55", "56+"];

export function levelRange(label: string): { min_level: number | null; max_level: number | null } {
  const range = /^(\d+)–(\d+)$/.exec(label);
  if (range) return { min_level: Number(range[1]), max_level: Number(range[2]) };
  const from = /^(\d+)\+$/.exec(label);
  if (from) return { min_level: Number(from[1]), max_level: null };
  return { min_level: null, max_level: null };
}

export const RANK_CHIPS: [string, string][] = [
  ["Все", ""], ["Обычные", "Обычный"], ["Элитные", "Элитный"], ["Героические", "Героический"], ["Легендарные", "Легендарный"],
];

export function rowSubtitle(row: Detail): string {
  const level = row.level === "" || row.level === null || row.level === undefined ? "" : `Ур. ${row.level}`;
  return [level, row.kind, row.rank].filter((part) => part).join(" · ");
}

export type Place = { map_id: string; count: number; gx: number; gy: number };

/** The NPC's first point in a zone and how many it has there; null when it has none. */
export function placeAt(detail: Detail, mapId: string): Place | null {
  const here: Detail[] = (Array.isArray(detail.points) ? detail.points : []).filter((point: Detail) => String(point.map_id) === mapId);
  return here.length ? { map_id: mapId, count: here.length, gx: Number(here[0].gx), gy: Number(here[0].gy) } : null;
}

/** The zone with the most points of the NPC (the first of equals) and its first point. */
export function mainPlace(detail: Detail): Place | null {
  const counts = new Map<string, number>();
  for (const point of (Array.isArray(detail.points) ? detail.points : []) as Detail[]) counts.set(String(point.map_id), (counts.get(String(point.map_id)) ?? 0) + 1);
  let best: [string, number] | null = null;
  for (const entry of counts) if (!best || entry[1] > best[1]) best = entry;
  return best ? placeAt(detail, best[0]) : null;
}

const HP_FRAMES: Record<number, [number, number, number, number]> = { 1: [25, 0, 297, 79], 2: [26, 98, 310, 188], 3: [5, 205, 333, 296], 4: [0, 322, 336, 420] };
// the emblem and the level, centred by eye on each rank's socket (checked on the sprite at 3x)
const HP_ICON_TOP: Record<number, number> = { 1: 22, 2: 25, 3: 25, 4: 25 };
const HP_ICON_LEFT: Record<number, number> = { 1: 30, 2: 24, 3: 27, 4: 27 };
const HP_LEVEL_TOP: Record<number, number> = { 1: 41, 2: 44, 3: 42, 4: 46 };
const HP_LEVEL_LEFT: Record<number, number> = { 1: 19, 2: 14, 3: 14, 4: 14 };
const HP_OF_RANK: Record<string, number> = { "Обычный": 1, "Элитный": 2, "Героический": 3, "Легендарный": 4 };

/**
 * The HP artwork of an NPC's card: the rank-specific bar of the sprite npc/hp-bars.png (not a live HP), as Pulse draws it.
 * `frame` is [x0, y0, x1, y1] in the sprite; the emblem goes in a circle at (iconLeft, iconTop), the level at its left.
 */
export function hpFrame(detail: Detail): { rank: number; frame: [number, number, number, number]; iconTop: number; iconLeft: number; levelTop: number; levelLeft: number } | null {
  const asked = detail.hp_bar || HP_OF_RANK[detail.rank as string];
  if (!asked) return null;
  const rank = asked in HP_FRAMES ? Number(asked) : 1;
  return { rank, frame: HP_FRAMES[rank], iconTop: HP_ICON_TOP[rank], iconLeft: HP_ICON_LEFT[rank], levelTop: HP_LEVEL_TOP[rank], levelLeft: HP_LEVEL_LEFT[rank] };
}

const KEY_STATS = ["Макс. ХП", "DP", "Опыт", "Ранг Бездны"];

/** The card's numbers: the key tiles (HP, DP, XP, abyss rank, as many as the NPC has) and the other facts; level and rank are in the header. */
export function statGroups(detail: Detail): { key: [string, string][]; rest: [string, string][] } {
  const rows = overviewRows(detail).filter(([name]) => name !== "Уровень" && name !== "Ранг").map(([name, value]) => [name, statText(value)] as [string, string]);
  const key = KEY_STATS.flatMap((name) => rows.filter(([row]) => row === name));
  return { key, rest: rows.filter(([name]) => !KEY_STATS.includes(name)) };
}

/** The tier of a rank, 1 plain … 4 legendary: the card's colour; 0 when the rank is not known. */
export function rankTier(rank: string | null | undefined): number {
  return (rank && HP_OF_RANK[rank]) || 0;
}

export function iconPath(asset: string | null | undefined): string | null {
  if (!asset) return null;
  return asset.includes("/") ? asset : `items/${asset}`; // a drop's icon comes without its folder
}

export function rarityClass(rarity: string | null | undefined): string {
  return `g-${rarity || "common"}`;
}

const ROLES: Record<string, string> = {
  merchant: "Торговец", coin_merchant: "Меняла", vendor: "Лавочник", teleport: "Телепорт", bindstone: "Кибелиск",
  warehouse: "Склад", stigma_master: "Мастер стигм", postbox: "Почта",
};

export function roleLabel(role: string | null | undefined): string {
  return (role && ROLES[role]) || "";
}
