/**
 * The gear calculator's data in pulse.db (schema 8, core/pulse_db/gear.py): what fits a slot, the manastones, the item sets.
 *
 *   gearChoices(all, "main", { cls: "fighter", levelMax: 55 }) -> GearItem[]   the items of a doll slot, filtered and sorted
 *   gearItem(all, id) -> GearItem | null
 *   gearStones(all, maxLevel) -> Stone[]
 *   gearSets(all, ids) -> GearSet[]
 */

import type { GearItem, GearSet, SlotKey, Stone } from "../gear/engine";
import type { All } from "./npcPoints";

/** A doll slot -> the item slots that fit it. */
export const SLOT_FITS: Record<SlotKey, string[]> = {
  main: ["main", "main_or_sub"], sub: ["sub", "main_or_sub"], head: ["head"], torso: ["torso"], pants: ["pants"], shoulder: ["shoulder"],
  glove: ["glove"], shoes: ["shoes"], earring1: ["earring"], earring2: ["earring"], ring1: ["ring"], ring2: ["ring"], necklace: ["necklace"],
  belt: ["belt"], wing: ["wing"],
};

export interface ChoiceOptions {
  cls?: string;          // only what this class may wear
  levelMin?: number;
  levelMax?: number;
  grade?: string;
  grp?: string;          // one group: «polearm», «pl_torso» …
  query?: string;        // a part of the name or the id
  limit?: number;
}

const row = (r: Record<string, any>): GearItem => ({
  id: Number(r.id), name: String(r.name), icon: String(r.icon ?? ""), grade: String(r.grade ?? ""), level: Number(r.level ?? 0), slot: String(r.slot),
  grp: String(r.grp), classes: JSON.parse(r.classes ?? "[]"), basic: JSON.parse(r.basic ?? "{}"), bonus: JSON.parse(r.bonus ?? "[]"),
  stones: r.stones === null || r.stones === undefined ? null : Number(r.stones), stonesBonus: r.stones_bonus === null || r.stones_bonus === undefined ? null : Number(r.stones_bonus),
  enchant: Boolean(r.enchant), setId: r.set_id === null || r.set_id === undefined ? null : Number(r.set_id),
});

const fold = (text: string) => text.toLowerCase().split("ё").join("е").trim();

/** The items of a doll slot: the newest first (level, then grade), at most `limit`. */
export async function gearChoices(all: All, slot: SlotKey, o: ChoiceOptions = {}): Promise<GearItem[]> {
  const where = ["slot IN (SELECT value FROM json_each(?))"];
  const args: unknown[] = [JSON.stringify(SLOT_FITS[slot])];
  if (slot === "sub") where.push("(grp = 'shield' OR slot = 'main_or_sub')");
  if (o.cls) { where.push("classes LIKE ?"); args.push(`%"${o.cls}"%`); }
  if (o.levelMin !== undefined) { where.push("level >= ?"); args.push(o.levelMin); }
  if (o.levelMax !== undefined) { where.push("level <= ?"); args.push(o.levelMax); }
  if (o.grade) { where.push("grade = ?"); args.push(o.grade); }
  if (o.grp) { where.push("grp = ?"); args.push(o.grp); }
  const query = fold(o.query ?? "");
  if (query) { where.push("(name_key LIKE ? OR CAST(id AS TEXT) = ?)"); args.push(`%${query}%`, query); }
  const rows = await all(
    `SELECT * FROM gear_item WHERE ${where.join(" AND ")} ORDER BY level DESC, `
    + "CASE grade WHEN 'mythic' THEN 0 WHEN 'epic' THEN 1 WHEN 'unique' THEN 2 WHEN 'legend' THEN 3 WHEN 'rare' THEN 4 WHEN 'common' THEN 5 ELSE 6 END, name LIMIT ?",
    [...args, o.limit ?? 200],
  );
  return rows.map(row);
}

/** The groups a slot's items come in, for the «Тип» filter. */
export async function gearGroups(all: All, slot: SlotKey, cls?: string): Promise<string[]> {
  const rows = await all(
    `SELECT DISTINCT grp FROM gear_item WHERE slot IN (SELECT value FROM json_each(?))${slot === "sub" ? " AND (grp = 'shield' OR slot = 'main_or_sub')" : ""}`
    + `${cls ? " AND classes LIKE ?" : ""} ORDER BY grp`,
    cls ? [JSON.stringify(SLOT_FITS[slot]), `%"${cls}"%`] : [JSON.stringify(SLOT_FITS[slot])],
  );
  return rows.map((r) => String(r.grp));
}

export async function gearItem(all: All, id: number): Promise<GearItem | null> {
  const [r] = await all("SELECT * FROM gear_item WHERE id = ?", [id]);
  return r ? row(r) : null;
}

export async function gearStones(all: All, maxLevel = 99): Promise<Stone[]> {
  const rows = await all("SELECT * FROM gear_stone WHERE level <= ? ORDER BY stat, value DESC", [maxLevel]);
  return rows.map((r) => ({ id: Number(r.id), name: String(r.name), icon: String(r.icon ?? ""), grade: String(r.grade ?? ""), level: Number(r.level ?? 0),
    stat: String(r.stat), value: Number(r.value) }));
}

export async function gearSets(all: All, ids: number[]): Promise<GearSet[]> {
  if (!ids.length) return [];
  const rows = await all("SELECT * FROM gear_set WHERE id IN (SELECT value FROM json_each(?))", [JSON.stringify([...new Set(ids)])]);
  return rows.map((r) => ({ id: Number(r.id), name: String(r.name), items: JSON.parse(r.items), bonuses: JSON.parse(r.bonuses) }));
}

/** The titles that give a bonus, by name: for the calculator's «Титул». */
export async function gearTitles(all: All): Promise<{ id: number; name: string; race: string; bonus: string[] }[]> {
  const rows = await all("SELECT id, name, race, stats FROM title WHERE name <> '' ORDER BY name_key").catch(() => []);
  return rows.map((r) => ({ id: Number(r.id), name: String(r.name), race: String(r.race ?? ""), bonus: (JSON.parse(r.stats ?? "{}").bonus ?? []) as string[] }))
    .filter((t) => t.bonus.length > 0);
}
