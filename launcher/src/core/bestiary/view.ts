/**
 * What the Bestiary screen shows of the store's rows and cards — pure, no window:
 *
 *   LEVELS / levelRange(label)   the «Уровень» choices and their bounds for BestiaryStore.search
 *   RANK_CHIPS                   the class chips: [label, rank of the database]
 *   rowSubtitle(row)             «Ур. 55 · Торговец · Обычный» under a list row's name
 *   mainPlace(detail)            the zone with the most points and its first point (the mini map, «Показать на карте»)
 *   iconPath(asset)              a picture's path inside the bestiary's icon folder (data/bestiary/icons)
 *   rarityClass(rarity)          the colour class of an item's name
 *   roleLabel(role)              the NPC's service in Russian (merchant -> «Торговец»)
 */

import type { Detail } from "./card";

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

export function mainPlace(detail: Detail): { map_id: string; count: number; gx: number; gy: number } | null {
  const points: Detail[] = Array.isArray(detail.points) ? detail.points : [];
  const counts = new Map<string, number>();
  for (const point of points) counts.set(String(point.map_id), (counts.get(String(point.map_id)) ?? 0) + 1);
  let best: [string, number] | null = null;
  for (const entry of counts) if (!best || entry[1] > best[1]) best = entry;
  if (!best) return null;
  const first = points.find((point) => String(point.map_id) === best![0])!;
  return { map_id: best[0], count: best[1], gx: Number(first.gx), gy: Number(first.gy) };
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
