/**
 * Quests, crafting recipes and the client's vendor lists from pulse.db (docs/ADR-002-pulse-db.md, stage 4), for the
 * chat's quest links and the tabs that show them (Крафт, the NPC card). Reading only; ids go out as strings.
 *
 *   questNames(all) -> id -> name           every quest, for chat links
 *   questsOf(all, npcId) -> Quest[]         the quests an NPC gives (role «giver») and takes back («ender»)
 *   recipe(all, id) -> Recipe | null        a recipe with its product and parts named
 *   recipesFor(all, itemId) / recipesUsing(all, itemId) -> Recipe[]   the recipes that make an item / that need it
 *   vendorItems(all, npcId) -> VendorItem[] what an NPC trades by the client's lists
 */

import type { All } from "./npcPoints";

type Row = Record<string, any>;

export interface ItemRef { id: string; name: string; grade: string; icon: string }
export interface Quest {
  id: string; name: string; role: "giver" | "ender"; min_level: number | null; max_level: number | null; races: string[];
  category: string; repeatable: boolean; rewards: Row[];
}
export interface Recipe {
  id: string; name: string; product: ItemRef | null; count: number; profession: string; level: number | null; race: string;
  combo: string[]; parts: (ItemRef & { count: number })[];
}
export interface VendorItem extends ItemRef { kind: string }

const ref = (id: unknown, row: Row | undefined): ItemRef =>
  ({ id: String(id), name: row?.name ?? "", grade: row?.grade ?? "", icon: row?.icon ?? "" });

/** The item rows of these ids, by id (one query). */
async function itemsById(all: All, ids: number[]): Promise<Map<number, Row>> {
  if (!ids.length) return new Map();
  const rows = await all("SELECT id, name, grade, icon FROM item WHERE id IN (SELECT value FROM json_each(?))", [JSON.stringify([...new Set(ids)])]);
  return new Map(rows.map((row) => [Number(row.id), row]));
}

export async function questNames(all: All): Promise<Record<string, string>> {
  const names: Record<string, string> = {};
  for (const row of await all("SELECT id, name FROM quest WHERE name <> ''")) names[String(row.id)] = row.name;
  return names;
}

export async function questsOf(all: All, npcId: string): Promise<Quest[]> {
  const rows = await all(
    "SELECT *, CASE WHEN giver = ? THEN 'giver' ELSE 'ender' END AS role FROM quest WHERE giver = ? OR ender = ? ORDER BY role DESC, id",
    [npcId, npcId, npcId],
  );
  return rows.map((q) => ({
    id: String(q.id), name: q.name, role: q.role, min_level: q.min_level, max_level: q.max_level,
    races: q.race ? String(q.race).split(",") : [], category: q.category ?? "", repeatable: Boolean(q.repeatable),
    rewards: q.rewards ? JSON.parse(q.rewards) : [],
  }));
}

/** The recipes of these rows with their products and parts named. */
async function recipes(all: All, rows: Row[]): Promise<Recipe[]> {
  if (!rows.length) return [];
  const parts = await all(
    "SELECT recipe_id, item_id, count FROM recipe_part WHERE recipe_id IN (SELECT value FROM json_each(?)) ORDER BY recipe_id, ord",
    [JSON.stringify(rows.map((r) => r.id))],
  );
  const items = await itemsById(all, [...rows.map((r) => r.product).filter((id) => id !== null), ...parts.map((p) => p.item_id)]);
  return rows.map((r) => ({
    id: String(r.id), name: r.name, product: r.product === null ? null : ref(r.product, items.get(Number(r.product))), count: r.count ?? 1,
    profession: r.profession ?? "", level: r.level, race: r.race ?? "", combo: r.combo ? JSON.parse(r.combo).map(String) : [],
    parts: parts.filter((p) => p.recipe_id === r.id).map((p) => ({ ...ref(p.item_id, items.get(Number(p.item_id))), count: p.count })),
  }));
}

export async function recipe(all: All, id: string): Promise<Recipe | null> {
  if (!/^\d+$/.test(id)) return null;
  const [found] = await recipes(all, await all("SELECT * FROM recipe WHERE id = ?", [Number(id)]));
  return found ?? null;
}

export async function recipesFor(all: All, itemId: string): Promise<Recipe[]> {
  return recipes(all, await all("SELECT * FROM recipe WHERE product = ? ORDER BY level, id", [Number(itemId)]));
}

export async function recipesUsing(all: All, itemId: string): Promise<Recipe[]> {
  return recipes(all, await all(
    "SELECT * FROM recipe WHERE id IN (SELECT recipe_id FROM recipe_part WHERE item_id = ?) ORDER BY level, id", [Number(itemId)]));
}

export async function vendorItems(all: All, npcId: string): Promise<VendorItem[]> {
  const rows = await all("SELECT item_id, kind FROM vendor_item WHERE npc_id = ? ORDER BY item_id", [npcId]);
  const items = await itemsById(all, rows.map((r) => Number(r.item_id)));
  return rows.map((r) => ({ ...ref(r.item_id, items.get(Number(r.item_id))), kind: r.kind }));
}
