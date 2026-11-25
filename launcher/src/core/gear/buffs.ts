/**
 * The skill buffs of the gear calculator, told apart by the class that casts them. Pure.
 *
 * Some skills have one id at two classes («Благословение жизни» 951 and «Благословение защиты» 955 at the cleric and the
 * chanter): a buff is therefore «class:id», and the two versions of one id never work together — turning one on turns the
 * other off.
 *
 *   buffKey("cleric", 951) -> "cleric:951"
 *   readBuffs(saved, cls, table) -> keys      saved: keys, or the bare numbers of builds saved before (the own class's
 *                                             skill first, else the first class that has it); unknown ones are dropped
 *   toggleBuff(keys, key) -> keys             off when on; else on, and the same id of another class goes off
 *   activeBuffs(keys, cls, level, table) -> Skill[]   for the arithmetic: the class's own skills and shared ones, at the level
 */
import { buffAt, type ActiveSkill, type Skill } from "./engine";

export type BuffTable = Record<string, ActiveSkill[]>;

export const buffKey = (owner: string, id: number) => `${owner}:${id}`;
const idOf = (key: string) => Number(key.slice(key.indexOf(":") + 1));

export function toggleBuff(keys: string[], key: string): string[] {
  if (keys.includes(key)) return keys.filter((k) => k !== key);
  return [...keys.filter((k) => idOf(k) !== idOf(key)), key];
}

export function readBuffs(saved: (string | number)[], cls: string, table: BuffTable): string[] {
  const has = (owner: string, id: number) => !!table[owner]?.some((s) => s.id === id);
  let out: string[] = [];
  for (const value of saved) {
    let key: string | null = null;
    if (typeof value === "number") {
      const owner = has(cls, value) ? cls : Object.keys(table).find((o) => has(o, value));
      key = owner ? buffKey(owner, value) : null;
    } else if (has(value.slice(0, value.indexOf(":")), idOf(value))) key = value;
    if (key) out = [...out.filter((k) => idOf(k) !== idOf(key!)), key];
  }
  return out;
}

export function activeBuffs(keys: string[], cls: string, level: number, table: BuffTable): Skill[] {
  const out: Skill[] = [];
  for (const [owner, skills] of Object.entries(table)) for (const skill of skills) {
    if (!keys.includes(buffKey(owner, skill.id)) || (owner !== cls && !skill.share)) continue;
    const step = buffAt(skill, level);
    if (step) out.push({ id: skill.id, name: step.name, effects: step.effects });
  }
  return out;
}
