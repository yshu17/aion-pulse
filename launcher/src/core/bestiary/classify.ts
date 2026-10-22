/**
 * Bestiary data hygiene: which records are technical, and where a record without spawn points can take them from —
 * the port of core/bestiary/bestiary_classify.py.
 *
 *     isMainNpc(badgeType, role, hasGoods)   merchant or functionary: the only NPCs listed for MAIN_ONLY_ZONES
 *     aboveMaxLevel(level, category)         a monster above level 55 (the server's cap), kept out of sight
 *     technicalName(name)                    test/internal names: «Test_…», «BAb1_…_lv50», English only, 3+ digits glued to letters
 *     plan(rows) -> [donors, service]        rows: id, name, level, category, points, drops, profile, sig (any JSON value)
 *
 * Known difference: Python's isdigit()/int() also take non-ASCII digits in levels; here only 0–9.
 */

import { casefold, pyOr, pyStr } from "../py";

const LATIN = /[A-Za-z]/;
const LATIN_ALL = /[A-Za-z]/g;
const CYRILLIC = /[А-Яа-яЁё]/;
const WORD = /[^\s\-,.()«»"']+/gu;
const ROMAN = /^[IVXLC]+$/;
// digits glued to letters: «NPC123», «Страж123» (Python's [^\W\d_] is a letter or a non-decimal numeric character)
const DIGIT_RUN = /[\p{L}\p{Nl}\p{No}]\p{Nd}{3,}|\p{Nd}{3,}[\p{L}\p{Nl}\p{No}]/u;
export const MAX_MOB_LEVEL = 55; // monsters above this level are not on the server yet: kept in the service group

/** A monster above MAX_MOB_LEVEL; a level that is not a number is never above it. */
export function aboveMaxLevel(level: unknown, category: string): boolean {
  const text = pyStr(pyOr(level, "")).trim();
  return category === "monster" && /^[0-9]+$/.test(text) && parseInt(text, 10) > MAX_MOB_LEVEL;
}

export const MAIN_ONLY_ZONES = new Set(["Элизиум"]); // zones listed for the NPCs a player deals with
export const MAIN_KINDS = new Set(["торговец", "функционер"]); // what the site calls them
export const MAIN_ROLES = new Set(["merchant", "coin_merchant", "vendor", "broker", "teleport", "warehouse", "stigma",
  "stigma_master", "postbox", "bindstone"]); // what the client says they do

/** Merchants and functionaries, not residents, guards or generic NPCs. A merchant with goods counts whatever its name. */
export function isMainNpc(badgeType: string, role: string, hasGoods: boolean): boolean {
  return hasGoods || MAIN_KINDS.has(casefold(badgeType.trim())) || MAIN_ROLES.has(casefold(role.trim()));
}

export const NEW_STATS = "новые характеристики ";

export function technicalName(name: string): boolean {
  const text = name.trim();
  if (!text || !/\p{L}/u.test(text)) return true; // empty or digits and punctuation only
  if (text.includes("_") || casefold(text).includes("test") || DIGIT_RUN.test(text)) return true;
  if (LATIN.test(text) && !CYRILLIC.test(text)) return true; // English names
  // a Latin word inside a Russian name; Roman numerals do not count, nor does one stray Latin letter («Барoшунг»)
  return (text.match(WORD) ?? []).some((word) => (word.match(LATIN_ALL) ?? []).length >= 2 && !ROMAN.test(word));
}

/** Word stems of a name, order-free, so «хранителя Валона» and «Хранитель Валон» agree. */
export function stemKey(name: string): string[] {
  const words = casefold(name).match(/[а-яёa-z0-9]+/g) ?? [];
  return words.map((w) => (w.length > 3 && "аяуюыиеоьй".includes(w[w.length - 1]) ? w.slice(0, -1) : w))
    .sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}

export interface PlanRow {
  id: string;
  name: string;
  level: unknown;
  category: string;
  points: number;
  drops: number;
  profile: number | boolean;
  sig: unknown[];
}

/**
 * donors: {npc id: donor id} — a record with no points takes them from a same-named record, or from the base of
 * «Новые характеристики …» (by word stems). service: technical names and duplicates (same name, level and category as
 * a better record with identical content, so no spawn place, drop or ware is lost).
 */
export function plan(rows: PlanRow[]): [Record<string, string>, Set<string>] {
  const withPoints = rows.filter((row) => row.points && !technicalName(row.name));
  const byName = new Map<string, PlanRow>();
  const byStem = new Map<string, PlanRow>();
  for (const row of [...withPoints].sort((a, b) => a.points - b.points)) { // the richest record wins
    byName.set(casefold(row.name), row);
    byStem.set(JSON.stringify(stemKey(row.name)), row);
  }
  const donors: Record<string, string> = {};
  const points = new Map(rows.map((row) => [row.id, row.points]));
  const sigs = new Map(rows.map((row) => [row.id, row.sig]));
  for (const row of rows) {
    if (row.points || technicalName(row.name)) continue;
    const key = casefold(row.name);
    let donor = byName.get(key);
    if (donor === undefined && key.startsWith(NEW_STATS)) donor = byStem.get(JSON.stringify(stemKey(row.name.slice(NEW_STATS.length))));
    if (donor && donor.id !== row.id) {
      donors[row.id] = donor.id;
      points.set(row.id, donor.points);
      sigs.set(row.id, [donor.sig[0], ...row.sig.slice(1)]); // own wares and drops, the donor's places
    }
  }
  const service = new Set(rows.filter((row) => technicalName(row.name)).map((row) => row.id));
  const groups = new Map<string, PlanRow[]>();
  for (const row of rows) {
    if (service.has(row.id)) continue;
    const key = JSON.stringify([casefold(row.name), pyStr(row.level), row.category, sigs.get(row.id)]);
    const group = groups.get(key);
    if (group) group.push(row);
    else groups.set(key, [row]);
  }
  const rank = (row: PlanRow): number[] => [Number(row.profile), points.get(row.id)!, row.drops];
  for (const group of groups.values()) {
    group.sort((a, b) => {
      const [x, y] = [rank(a), rank(b)];
      for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return y[i] - x[i];
      return 0;
    });
    for (const row of group.slice(1)) service.add(row.id);
  }
  return [donors, service];
}
