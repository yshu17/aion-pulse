/**
 * What the NPC card says, from a BestiaryStore.detail() object: stats, description, places, drops and the merchant
 * stock — the port of core/bestiary/card.py. Objects in, text out.
 *
 *     overviewRows(detail) -> [[name, value]]           level, rank, stats, faction, race
 *     overviewText(detail)                              title, description and the merchant's trade sections
 *     placeCounts(detail, mapNames) -> [[map id, n]]    spawn points per zone, sorted by zone name
 *     locationsText / pointsFromText / dropsEmptyText   the «Локации» and «Добыча» blocks
 *     filterDrops(detail, query) and dropsNote(shown, detail); filterStock(detail, query) and stockNote(shown, total)
 */

import { casefold, pyStr } from "../py";

export type Detail = Record<string, any>;

export const CATEGORY: Record<string, string> = {
  "Все группы": "", "Монстры": "monster", "NPC": "npc", "Торговцы": "merchant", "Служебные": "service", "Низкоуровневые": "low",
};
export const SORTS: Record<string, string> = {
  "Сначала с профилем": "", "Уровень ↑": "level_asc", "Уровень ↓": "level_desc", "Имя А → Я": "name_asc", "Имя Я → А": "name_desc",
};
export const RARITY: Record<string, string> = {
  junk: "Простой", common: "Обычный", rare: "Редкий", legend: "Легендарный", unique: "Уникальный", epic: "Эпический",
  mythic: "Мифический",
};
export const KB_ITEM_URL = "https://kb.aionempire.com/items/{}";

/** Python truthiness of a JSON value. */
const truthy = (v: unknown): boolean =>
  !(v === null || v === undefined || v === false || v === 0 || v === "" || (Array.isArray(v) && !v.length)
    || (typeof v === "object" && v !== null && !Array.isArray(v) && !Object.keys(v).length));
const or = <T>(v: unknown, fallback: T) => (truthy(v) ? v : fallback);

export function overviewRows(detail: Detail): [string, unknown][] {
  const stats = or(detail.stats, {}) as Record<string, unknown>;
  return [["Уровень", or(detail.level, "Не указан")], ["Ранг", or(detail.rank, "Не указан")], ...Object.entries(stats),
    ["Принадлежность", or(detail.faction, "Другие")], ["Вид", or(detail.race, "Не указан")]];
}

export function overviewText(detail: Detail): string {
  let text = [detail.title, detail.description].filter(truthy).join("\n");
  if (truthy(detail.stock)) {
    const groups = [...new Set((detail.stock as Detail[]).map((item) => item.group ?? ""))];
    text += "\nТорговые разделы: " + groups.filter(truthy).join(", ");
  }
  return text.trim();
}

export function placeCounts(detail: Detail, mapNames: Record<string, string>): [string, number][] {
  const counts = new Map<string, number>();
  for (const point of (or(detail.points, []) as Detail[])) {
    const id = pyStr(or(point.map_id, ""));
    counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  const name = (id: string) => (Object.prototype.hasOwnProperty.call(mapNames, id) ? mapNames[id] : id);
  return [...counts].sort((a, b) => (name(a[0]) < name(b[0]) ? -1 : name(a[0]) > name(b[0]) ? 1 : 0));
}

export function dropsEmptyText(detail: Detail): string {
  return detail.kb_status === "loaded" ? "В профиле KB нет списка добычи." : "Сведения о добыче пока не загружены.";
}

/** The «Локации» block without spawn points: the KB locations, or a note that the client has none. */
export function locationsText(detail: Detail): string {
  const names = (or(detail.kb_locations, []) as Detail[]).map((loc) => or(loc.name, undefined) ?? loc.slug);
  return names.some(truthy) ? "По базе KB: " + names.filter(truthy).join(", ") : "Точки появления в файлах клиента не найдены.";
}

export function pointsFromText(detail: Detail): string {
  return truthy(detail.points_from) ? `Места взяты у одноимённой записи «${detail.points_from}».` : "";
}

export function filterDrops(detail: Detail, query: string): [number, Detail][] {
  const term = casefold(query.trim());
  return (or(detail.drops, []) as Detail[]).map((item, i) => [i, item] as [number, Detail])
    .filter(([, item]) => casefold(pyStr(or(item.name, ""))).includes(term));
}

export function dropsNote(shown: number, detail: Detail): string {
  const total = (or(detail.drops, []) as unknown[]).length;
  if (total) return `Показано ${shown} из ${total}. Шансы выпадения не указаны.`;
  return detail.kb_status === "loaded" ? "В профиле нет списка добычи." : "Сведения о добыче пока не загружены.";
}

export function filterStock(detail: Detail, query: string): [number, Detail][] {
  const term = casefold(query.trim());
  return (or(detail.stock, []) as Detail[]).map((item, i) => [i, item] as [number, Detail])
    .filter(([, item]) => casefold(`${item.name ?? ""} ${item.group ?? ""}`).includes(term));
}

export function stockNote(shown: number, total: number): string {
  if (total) return `Показано ${shown} из ${total}. Ассортимент из клиента; на сервере возможны отличия.`;
  return "Для этого NPC список товаров в клиенте не найден.";
}
