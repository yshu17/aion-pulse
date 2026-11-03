/**
 * The items from pulse.db (docs/ADR-002-pulse-db.md, stage 3): the names of chat links, the catalog of item cards and
 * their descriptions, in the shapes the screens took from item_names.tsv, watch_items.csv and item_specs.json.gz.
 *
 *   itemCatalog(all) -> { names, catalog }   names: id -> name of every item; catalog: the items with a card, in order
 *   itemSpecs(all) -> (id) -> spec | null    a card's description (item.spec, deflated with meta «spec_dict»)
 */

import { inflate } from "pako";

import type { WatchItem } from "../items/catalog";
import type { Spec } from "../items/specs";
import type { All } from "./npcPoints";

type Bytes = Uint8Array | number[]; // the program's answer gives a BLOB as numbers, sql.js and node as bytes

const bytes = (value: Bytes) => (value instanceof Uint8Array ? value : Uint8Array.from(value));

export async function itemCatalog(all: All): Promise<{ names: Record<string, string>; catalog: WatchItem[] }> {
  const [named, carded] = await Promise.all([
    all("SELECT id, name FROM item WHERE name <> ''"),
    all("SELECT id, name, level, category, grade, icon, kind FROM item WHERE catalog_ord IS NOT NULL ORDER BY catalog_ord"),
  ]);
  const names: Record<string, string> = {};
  for (const row of named) names[String(row.id)] = row.name;
  const catalog = carded.map((row): WatchItem => ({
    id: String(row.id), name: row.name, level: row.level ?? NaN, category: row.category ?? "Прочее",
    grade: row.grade ?? "", icon: row.icon ?? "", kind: row.kind ?? "",
  }));
  return { names, catalog };
}

/** Reads one description at a time; the dictionary is read on the first. */
export function itemSpecs(all: All): (id: string) => Promise<Spec | null> {
  let dictionary: Promise<Uint8Array | null> | null = null;
  return async (id) => {
    if (!/^\d+$/.test(id)) return null;
    dictionary ??= all("SELECT value FROM meta WHERE key = 'spec_dict'").then(([row]) => (row ? bytes(row.value) : null));
    const [[row], dict] = await Promise.all([all("SELECT spec FROM item WHERE id = ?", [Number(id)]), dictionary]);
    if (!row?.spec || !dict) return null;
    return JSON.parse(new TextDecoder().decode(inflate(bytes(row.spec), { dictionary: dict })));
  };
}
