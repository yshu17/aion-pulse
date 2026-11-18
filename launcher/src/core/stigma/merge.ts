/**
 * The stigma calculator's two sources, in this order: the data of github.com/Persepha/Aion-classic-stigma-calculator
 * (data/stigma/classic24.json: which stigmas a class has, their levels, trees, needs, costs, MP, cast and cooldown), then
 * pulse.db, the game client's (the Russian name, the text with this server's numbers from skill_damage, the icon, the stone
 * item and the levels the calculator does not list). A level's skill id is the client's in both, so they meet on it.
 */

import type { All } from "../db/npcPoints";
import { cleanSkillText } from "../items/statNames";
import type { Faction, Stigma, StigmaLevel } from "./calc";

export type GitStigma = Omit<Stigma, "levels"> & { levels: Omit<StigmaLevel, "icon" | "stone" | "fromDb">[] };

export interface DbSkill { id: number; internal_name: string; name: string | null; description: string | null; damage: string | null; icon: string | null }
export interface DbStone extends Omit<DbSkill, "id"> {
  item_id: number; skill_id: number; level: number; requires?: string | null;
  // pulse.db schema 10: the stone's classes (JSON {class: level}), races, stigma shards, abyss points, kinah, advanced (1)
  classes?: string | null; races?: string | null; shards?: number | null; ap?: number | null; price?: number | null; advanced?: number | null;
}

/** «KN_BreakPower_G4» -> «kn_breakpower»: the client's skill without its level, the calculator's stigma id most of the time. */
export const family = (internalName: string) => internalName.toLowerCase().replace(/_g\d+$/, "");

/** The database's text when it is whole: the resolved one (skill_damage), else the description without «[%…]» blanks. */
const dbText = (s: { description: string | null; damage: string | null } | undefined) =>
  s?.damage || (s?.description && !s.description.includes("[%") ? s.description : "") || "";

/**
 * The stigma's family in the client: its id when stones of that name exist, else the name most of its levels' skills share
 * (the calculator writes «ra_heavenstrap_dark», the client «RA_Dark_HeavensTrap_G1»).
 */
function familyOf(g: GitStigma, skill: Map<number, DbSkill>, families: Set<string>): string {
  if (families.has(g.id)) return g.id;
  const count = new Map<string, number>();
  for (const l of g.levels) {
    const name = skill.get(l.skill)?.internal_name;
    if (name) count.set(family(name), (count.get(family(name)) ?? 0) + 1);
  }
  return [...count].sort((a, b) => b[1] - a[1])[0]?.[0] ?? g.id;
}

/** The stones by skill id (the lowest one of a skill), and each stigma's family in the client. */
function index(git: GitStigma[], skills: DbSkill[], stones: DbStone[]) {
  const skill = new Map(skills.map((s) => [s.id, s]));
  const stoneOf = new Map<number, DbStone>();
  for (const st of [...stones].sort((a, b) => a.level - b.level)) if (!stoneOf.has(st.skill_id)) stoneOf.set(st.skill_id, st);
  const families = new Set([...stoneOf.values()].map((st) => family(st.internal_name)));
  return { skill, stoneOf, famOf: new Map(git.map((g) => [g.id, familyOf(g, skill, families)])) };
}

export function mergeStigmas(git: GitStigma[], skills: DbSkill[], stones: DbStone[]): Stigma[] {
  const { skill, stoneOf, famOf } = index(git, skills, stones);
  return git.map((g) => {
    const fam = famOf.get(g.id)!;
    const own = [...stoneOf.values()].filter((st) => family(st.internal_name) === fam);
    const levels: StigmaLevel[] = g.levels.map((l) => {
      let id = l.skill;
      const name = skill.get(id)?.internal_name;
      // the calculator's id names a skill of another stigma: the stone of this one at that level has the right one
      if (name && family(name) !== fam) id = own.find((st) => st.level === l.level)?.skill_id ?? id;
      const db = id === l.skill ? skill.get(id) ?? stoneOf.get(id) : stoneOf.get(id);
      const st = stoneOf.get(id);
      return { ...l, skill: id, name: db?.name || l.name, text: dbText(db) || l.text, icon: db?.icon || "", stone: st?.item_id ?? null,
        shards: l.shards ?? st?.shards ?? null, price: st?.price ?? null };
    });
    for (const st of own) {
      if (levels.some((l) => l.skill === st.skill_id || l.level === st.level)) continue;
      levels.push(stoneLevel(st, st.level));
    }
    levels.sort((a, b) => a.level - b.level);
    const anyIcon = levels.find((l) => l.icon)?.icon ?? "";
    for (const l of levels) if (!l.icon) l.icon = anyIcon;
    return { ...g, levels };
  });
}

/** A level made of a stone alone (the calculator does not have it): the client's numbers, no MP, cast or cooldown. */
function stoneLevel(st: DbStone, level: number): StigmaLevel {
  return { level, skill: st.skill_id, name: st.name || st.internal_name, text: dbText(st) || cleanSkillText(st.description ?? ""), mp: "", cast: "", cooldown: "",
    shards: st.shards ?? null, ap: st.ap ?? 0, price: st.price ?? null, icon: st.icon || "", stone: st.item_id, fromDb: true };
}

const BASE: Record<string, string[]> = { warrior: ["fighter", "knight"], scout: ["assassin", "ranger"], mage: ["wizard", "elementalist"],
  priest: ["cleric", "chanter"] };
const OWN = new Set(Object.values(BASE).flat());
const PREFIX: Record<string, string> = { fi: "fighter", kn: "knight", as: "assassin", ra: "ranger", wi: "wizard", el: "elementalist", ch: "chanter", pr: "cleric" };

/**
 * The calculator's classes that wear a stone, with the character's level: the client's own class columns, a base class
 * (warrior, scout, mage, priest) for both of its classes; a class's skill («PR_…») stays with that class.
 */
export function classesOf(classes: string | null | undefined, internalName: string): Record<string, number> {
  let raw: Record<string, number>;
  try { raw = JSON.parse(classes ?? "{}") ?? {}; } catch { return {}; }
  const out: Record<string, number> = {};
  for (const [c, lv] of Object.entries(raw)) for (const x of BASE[c] ?? (OWN.has(c) ? [c] : [])) out[x] = Math.max(out[x] ?? 0, lv);
  const own = PREFIX[internalName.slice(0, internalName.indexOf("_")).toLowerCase()];
  return own && own in out ? { [own]: out[own] } : out;
}

/**
 * The stigmas of a class and faction that only pulse.db has: the stones no calculator stigma (of any class) claims, one stigma
 * per client skill without its level. Their places are not in a tree; they need what their stones say.
 */
export function clientStigmas(cls: string, faction: Faction, allGit: GitStigma[], skills: DbSkill[], stones: DbStone[]): Stigma[] {
  const { stoneOf, famOf } = index(allGit, skills, stones);
  const claimed = new Set(famOf.values());
  const groups = new Map<string, DbStone[]>();
  for (const st of stoneOf.values()) {
    const fam = family(st.internal_name);
    const races = st.races ?? "pc_light pc_dark";
    if (claimed.has(fam) || !(cls in classesOf(st.classes, st.internal_name))) continue;
    if (!races.includes(faction === "elyos" ? "pc_light" : "pc_dark")) continue;
    groups.set(fam, [...(groups.get(fam) ?? []), st]);
  }
  return [...groups].map(([fam, list]) => {
    const races = list[0].races ?? "pc_light pc_dark";
    const levels: StigmaLevel[] = [];
    for (const st of list) {
      const at = classesOf(st.classes, st.internal_name)[cls] || st.level;
      if (!levels.some((l) => l.level === at)) levels.push(stoneLevel(st, at));
    }
    levels.sort((a, b) => a.level - b.level);
    return { id: fam, faction: races.includes("pc_light") && races.includes("pc_dark") ? "daeva" : races.includes("pc_light") ? "elyos" : "asmodian",
      advanced: list.some((st) => !!st.advanced), kind: "", target: "", info: [], levels, onlyClient: true };
  }).sort((a, b) => a.levels[0].level - b.levels[0].level || a.id.localeCompare(b.id));
}

/**
 * The class's dependencies: the calculator's, and for a stigma whose stone in the client lists what it needs (pulse.db
 * stigma.requires), the client's list, when each of its names is a stigma of the given list (one class, one faction).
 */
export function mergeNeeds(git: GitStigma[], needs: [string, string][], skills: DbSkill[], stones: DbStone[]): [string, string][] {
  const { famOf } = index(git, skills, stones);
  const idOf = new Map([...famOf].map(([id, fam]) => [fam, id]));
  const client = new Map<string, string[]>();
  for (const st of [...stones].sort((a, b) => a.level - b.level)) {
    const id = idOf.get(family(st.internal_name));
    if (!id || client.has(id) || !st.requires) continue;
    let list: [string, unknown, unknown][];
    try { list = JSON.parse(st.requires); } catch { continue; }
    const ids = list.map(([names]) => idOf.get(family(String(names).split(",")[0].trim())));
    if (ids.length && ids.every((x): x is string => !!x)) client.set(id, ids);
  }
  const out: [string, string][] = [];
  const done = new Set<string>();
  const emit = (id: string) => { if (!done.has(id)) { done.add(id); for (const n of client.get(id)!) out.push([id, n]); } };
  for (const [s, n] of needs) if (client.has(s)) emit(s); else out.push([s, n]);
  for (const id of client.keys()) emit(id);
  return out;
}

/** The pulse.db rows the merge needs: the skills of the given ids and every stigma stone with its skill. */
export async function readDb(all: All, ids: number[]): Promise<{ skills: DbSkill[]; stones: DbStone[] }> {
  const skills = ids.length ? await all(
    `SELECT s.id, s.internal_name, s.name, s.description, d.text AS damage, s.icon FROM skill s LEFT JOIN skill_damage d ON d.skill_id = s.id WHERE s.id IN (${ids.map(() => "?").join(",")})`,
    ids) : [];
  const from = "FROM stigma g JOIN skill s ON s.id = g.skill_id JOIN item i ON i.id = g.item_id LEFT JOIN skill_damage d ON d.skill_id = g.skill_id";
  const base = "g.item_id, g.skill_id, s.internal_name, i.level, g.requires, s.name, s.description, d.text AS damage, s.icon";
  // a database before schema 10 has no stone columns: the names, texts and icons still come, the prices and the client's own stigmas do not
  const stones = await all(`SELECT ${base}, g.classes, g.races, g.shards, g.ap, g.price, g.advanced ${from}`)
    .catch(() => all(`SELECT ${base} ${from}`));
  return { skills: skills as DbSkill[], stones: stones as DbStone[] };
}
