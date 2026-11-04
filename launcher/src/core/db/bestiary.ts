/**
 * The «NPC / Бестиарий» tab from pulse.db (docs/ADR-002-pulse-db.md, stage 2): the search, the card and the areas, in the
 * shapes the tab took from the old store (core/bestiary/store.ts over npcs.sqlite). Reading only: no SQL functions of
 * its own and no temporary tables (the program's db_query refuses writes); the Russian order is the column sort_key.
 *
 *   search(all, options) -> [rows, total]   rows: id, name, kind, race, rank, level, icon_asset, zone_names, faction,
 *                                           point_count, drop_count, has_profile, sold, dropped
 *   detail(all, id) -> card | null          the card's fields, its profile (stats, kb_*, trade_tabs …), stock, drops, points
 *   areas(all, id)                          the approximate spawn areas
 */

import { LOW_LEVEL, searchKey, type SearchOptions } from "../bestiary/store";
import { FACTIONS } from "../bestiary/labels";
import { pointsOf, type All } from "./npcPoints";
import { unpackIds } from "./packed";

type Row = Record<string, any>;

const ORDERS: Record<string, string> = {
  "": "n.has_profile DESC,n.point_count DESC,n.sort_key,n.id",
  level_asc: "n.level IS NULL,n.level,n.sort_key,n.id", // no level: at the end either way
  level_desc: "n.level IS NULL,n.level DESC,n.sort_key,n.id",
  name_asc: "n.sort_key,n.id",
  name_desc: "n.sort_key DESC,n.id",
};

const like = (text: string) => `%${text.replace(/\\/g, "\\\\").replace(/%/g, "\\%").replace(/_/g, "\\_")}%`;
const marks = (n: number) => Array.from({ length: n }, () => "?").join(",");

export async function search(all: All, options: SearchOptions = {}): Promise<[Row[], number]> {
  const { text = "", category = "", race = "", rank = "", map_id = "", offset = 0, limit = 150, min_level = null,
    max_level = null, region = "", order = "", hide_low = false } = options;
  const clauses = ["n.listed = 1", "n.service = ?"];
  const params: unknown[] = [category === "service" ? 1 : 0];
  const term = searchKey(text);
  const folded = term.replace(/ё/g, "е"); // the names' keys hold «ё» as «е»
  const byItem = Boolean(term) && !/^\p{Nd}+$/u.test(term);
  const soldSearch = ["merchant", ""].includes(category) && byItem;
  const dropSearch = ["monster", ""].includes(category) && byItem;
  // the items whose name holds the words, each with the NPCs that drop it (item.dropped_by): a mob is found by its drop
  const droppedBy: [string, Set<number>][] = dropSearch
    ? (await all("SELECT name, dropped_by FROM item WHERE name_key LIKE ? ESCAPE '\\' AND dropped_by IS NOT NULL ORDER BY length(name)", [like(folded)]))
      .map((item): [string, Set<number>] => [item.name, new Set(unpackIds(item.dropped_by, true))])
    : [];
  if (term) {
    // every name and the id; a merchant also by an item it sells, a mob by an item it drops
    const options = ["n.search_text LIKE ? ESCAPE '\\'", "n.sort_key LIKE ? ESCAPE '\\'"];
    params.push(like(term), like(folded));
    if (soldSearch) {
      options.push("EXISTS (SELECT 1 FROM npc_stock s WHERE s.npc_id = n.id AND s.name_key LIKE ? ESCAPE '\\')");
      params.push(like(folded));
    }
    if (droppedBy.length) {
      const ids = new Set<string>();
      for (const [, npcs] of droppedBy) for (const id of npcs) ids.add(String(id));
      options.push("n.id IN (SELECT value FROM json_each(?))");
      params.push(JSON.stringify([...ids]));
    }
    clauses.push("(" + options.join(" OR ") + ")");
  }
  const low = `(n.category = 'monster' AND n.level IS NOT NULL AND n.level < ${LOW_LEVEL})`;
  if (category === "low") clauses.push(low);
  else if (hide_low) clauses.push(`NOT ${low}`);
  if (category === "monster") clauses.push("n.category = 'monster'");
  else if (category === "npc") clauses.push("n.category = 'npc'");
  else if (category === "merchant") clauses.push("(n.role = 'merchant' OR n.kind = 'Торговец')");
  if (race) {
    clauses.push(FACTIONS.includes(race) ? "n.faction = ?" : "n.race = ?");
    params.push(race);
  }
  if (rank) {
    clauses.push("n.rank = ?");
    params.push(rank);
  }
  if (map_id) {
    clauses.push("EXISTS (SELECT 1 FROM npc_zone z WHERE z.npc_id = n.id AND z.map_id = ?)");
    params.push(map_id);
  }
  if (min_level !== null || max_level !== null) clauses.push("n.level IS NOT NULL");
  if (min_level !== null) { clauses.push("n.level >= ?"); params.push(min_level); }
  if (max_level !== null) { clauses.push("n.level <= ?"); params.push(max_level); }
  if (region) {
    clauses.push("EXISTS (SELECT 1 FROM npc_region r WHERE r.npc_id = n.id AND r.name = ?" + (map_id ? " AND r.map_id = ?" : "") + ")");
    params.push(region);
    if (map_id) params.push(map_id);
  }
  const where = " WHERE " + clauses.join(" AND ");
  const [{ n: total }] = await all("SELECT count(*) AS n FROM npc n" + where, params);
  const rows = (await all(
    "SELECT n.id, n.name, n.kind, n.race, n.rank, n.level, n.icon AS icon_asset, n.zone_names, n.faction, n.point_count, n.drop_count, "
    + "n.has_profile FROM npc n" + where + " ORDER BY " + (ORDERS[order] ?? ORDERS[""]) + " LIMIT ? OFFSET ?",
    [...params, limit, offset],
  )).map((row): Row => ({ ...row, icon_asset: row.icon_asset ?? "", sold: "", dropped: "" }));
  // the sold or dropped item that matched, shown under the name (when the name itself does not hold the words)
  const others = byItem ? rows.filter((row) => !String(row.name).toLowerCase().replace(/ё/g, "е").includes(folded)) : [];
  if (others.length) {
    const ids = others.map((row) => row.id);
    const first = (found: Row[]) => {
      const by = new Map<string, string>();
      for (const hit of found) if (!by.has(String(hit.npc_id))) by.set(String(hit.npc_id), hit.name); // drop links hold numbers
      return by;
    };
    const sold = soldSearch ? first(await all(`SELECT npc_id, name FROM npc_stock WHERE npc_id IN (${marks(ids.length)}) AND name_key LIKE ? ESCAPE '\\' ORDER BY length(name), ord`, [...ids, like(folded)])) : new Map();
    for (const row of others) {
      row.sold = sold.get(row.id) ?? "";
      if (!row.sold) row.dropped = droppedBy.find(([, npcs]) => npcs.has(Number(row.id)))?.[0] ?? "";
    }
  }
  return [rows, Number(total)];
}

export async function detail(all: All, npcId: string): Promise<Row | null> {
  const [row] = await all("SELECT * FROM npc WHERE id = ? AND listed = 1", [String(npcId)]);
  if (!row) return null;
  const dropIds = unpackIds(row.drops); // in the card's order
  const [stock, items, points] = await Promise.all([
    all("SELECT s.item_id, s.name, s.rarity, s.level, s.icon, s.grp, s.trade_mode, i.icon AS catalog_icon FROM npc_stock s LEFT JOIN item i ON i.id = CAST(s.item_id AS INTEGER) WHERE s.npc_id = ? ORDER BY s.ord", [row.id]),
    dropIds.length ? all("SELECT id, name, grade AS rarity, drop_icon AS icon, icon AS catalog_icon FROM item WHERE id IN (SELECT value FROM json_each(?))", [JSON.stringify(dropIds)]) : Promise.resolve([]),
    pointsOf(all, row.id),
  ]);
  const byId = new Map(items.map((item) => [Number(item.id), item]));
  const drops = dropIds.map((id) => byId.get(id) ?? { id, name: "", rarity: "", icon: "", catalog_icon: "" });
  const profile = row.profile ? JSON.parse(row.profile) : {};
  return {
    ...profile,
    id: row.id, name: row.name, internal_name: row.internal_name ?? "", category: row.category ?? "", role: row.role ?? "",
    title: row.title ?? "", description: row.description ?? "", race: row.race ?? "", faction: row.faction ?? "", kind: row.kind ?? "",
    rank: row.rank ?? "", level: row.level ?? "", hp_bar: row.hp_bar, icon_asset: row.icon ?? "",
    stock: stock.map((s) => ({ item_id: s.item_id, name: s.name, rarity: s.rarity, level: s.level, icon_asset: s.icon, catalog_icon: s.catalog_icon, group: s.grp, trade_mode: s.trade_mode })),
    drops: drops.map((d) => ({ item_id: String(d.id), name: d.name, rarity: d.rarity, icon: d.icon, catalog_icon: d.catalog_icon })),
    points: points.map((p) => ({ map_id: p.map_id, gx: p.x, gy: p.y, gz: p.z, source: p.source })),
  };
}

export async function areas(all: All, npcId: string): Promise<Row[]> {
  return (await all(
    "SELECT map_id, area_id, point_count, center_x, center_y, names, polygon FROM npc_area WHERE npc_id = ? ORDER BY point_count DESC, area_id",
    [String(npcId)],
  )).map((r) => ({ map_id: r.map_id, area_id: r.area_id, point_count: r.point_count, center: [r.center_x, r.center_y],
    names: JSON.parse(r.names), polygon: JSON.parse(r.polygon) }));
}
