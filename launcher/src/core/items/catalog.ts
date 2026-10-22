/**
 * Item data: id -> name catalog, the list of items the user can watch, names for chat links — the port of
 * core/items/catalog.py. Pure: every parser takes the file's text (null for a missing file gives empty data).
 */

export const CATEGORY_ORDER = [
  "Лата", "Кольчуга", "Кожа", "Ткань", "Оружие", "Щиты", "Крылья", "Украшения", "Головные уборы",
  "Изготовление", "Припасы", "Прочее",
];
/** In the catalog (chat links, tooltips) but not in the «Что искать» list. */
export const UNLISTED_CATEGORIES = new Set(["Изготовление", "Припасы", "Прочее"]);
export const UNLISTED_GRADES = new Set(["common", "rare", "junk"]); // white and green items
const ARMOR: Record<string, string> = {
  "Латная броня": "Лата",
  "Кольчужная броня": "Кольчуга",
  "Кожаная броня": "Кожа",
  "Тканая броня": "Ткань",
};
const WEAPONS = new Set(["Меч", "Булава", "Кинжал", "Орб", "Гримуар", "Двуручный меч", "Копье", "Посох", "Лук"]);

export interface WatchItem {
  id: string;
  name: string;
  level: number;
  category: string;
  grade: string;
  icon: string; // file name in data/icons (shared by items with the same picture)
  kind: string; // finer type for the filter: weapon type («Меч»), accessory type («Кольца»)
}

/** Group for the item list, from the site's «Тип» field (shields and wings have none). */
export function categoryFor(itemType: string, name: string): string {
  if (itemType in ARMOR) return ARMOR[itemType];
  if (WEAPONS.has(itemType)) return "Оружие";
  const lowered = name.toLowerCase();
  if (lowered.includes("щит")) return "Щиты";
  if (lowered.includes("крыль")) return "Крылья";
  return "Прочее";
}

/** Shown in the «Что искать» list: no white/green items, no materials, supplies or misc. */
export function isListed(item: WatchItem): boolean {
  return !UNLISTED_CATEGORIES.has(item.category) && !UNLISTED_GRADES.has(item.grade);
}

function lines(text: string): string[] {
  return text.split(/\r\n|\n|\r/);
}

/** `id<TAB>name` lines (ids are digits); used for item, map and quest names. */
export function parseNames(text: string | null): Record<string, string> {
  const names: Record<string, string> = {};
  if (text === null) return names;
  for (const line of lines(text)) {
    const tab = line.indexOf("\t");
    if (tab < 0) continue;
    const id = line.slice(0, tab);
    if (!/^\d+$/.test(id)) continue;
    names[id] = line.slice(tab + 1).trim();
  }
  return names;
}

/** Map and quest names for chat links, from map_names.tsv and quest_names.tsv. */
export function parseLinkNames(mapNames: string | null, questNames: string | null): [Record<string, string>, Record<string, string>] {
  return [parseNames(mapNames), parseNames(questNames)];
}

/** One CSV record per row (RFC 4180: quoted fields, doubled quotes, commas and line breaks inside quotes). */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else quoted = false;
      } else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += ch;
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

/** watch_items.csv (header id,name,level[,category,grade,icon,kind]); a missing file gives an empty list. */
export function parseWatchItems(text: string | null): WatchItem[] {
  if (text === null) return [];
  const [header, ...rows] = parseCsv(text.replace(/^﻿/, ""));
  if (!header) return [];
  return rows
    .filter((row) => row.length > 1 || row[0] !== "")
    .map((row) => {
      const get = (key: string) => {
        const index = header.indexOf(key);
        return index >= 0 && index < row.length ? row[index] : "";
      };
      return {
        id: get("id"),
        name: get("name"),
        level: parseInt(get("level"), 10),
        category: get("category") || "Прочее",
        grade: get("grade") || "",
        icon: get("icon") || "",
        kind: get("kind") || "",
      };
    });
}
