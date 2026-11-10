/**
 * The client's stat keys («maxHp 20», «PhysicalDefend 5» of client_titles) as the game shows them. Pure.
 *
 *   bonusLine("maxHp 20") -> ["Макс. HP", "+20"]
 *   bonusLine("speed 10") -> ["Скорость движения", "+10%"]
 *   cleanSkillText("урон [%e1.SkillATK.MinDamage]-…") -> "урон …"   the client's placeholders out
 *
 * The keys come in any case (maxHp, MaxHP, maxhp); an unknown key keeps its own name.
 */

import { statValue } from "./card";

/** key (lower case) -> the game's name, and whether the value is a percent. */
const NAMES: Record<string, [string, boolean]> = {
  speed: ["Скорость движения", true], flyspeed: ["Скорость полёта", true], boostcastingtime: ["Время каста", true],
  attackdelay: ["Задержка атаки", true], maxhp: ["Макс. HP", false], maxmp: ["Макс. MP", false], maxfp: ["Макс. время полёта", false],
  magicalskillboost: ["Сила магии", false], magicalhitaccuracy: ["Точн. маг.", false], phyattack: ["Физ. атака", false],
  critical: ["Ф. крит.", false], magicalcritical: ["Маг. крит.", false], magicalresist: ["Сопр. магии", false],
  pvpdefendratio: ["Защита в ПвП", false], pvpattackratio: ["Урон в ПвП", false], physicaldefend: ["Физ. защита", false],
  dodge: ["Уклонение", false], hitaccuracy: ["Точность", false], block: ["Блок щитом", false], parry: ["Парирование", false],
  healskillboost: ["Сила исцеления", false], hpregen: ["Восст. HP", false], mpregen: ["Восст. MP", false], boosthate: ["Агрессия", false],
  edfire: ["Защита от огня", false], edair: ["Защита от ветра", false], edearth: ["Защита от земли", false], edwater: ["Защита от воды", false],
};

export function bonusLine(text: string): [string, string] {
  const [key, ...rest] = String(text).trim().split(/\s+/);
  const raw = rest.join(" ");
  const known = NAMES[key.toLowerCase()];
  if (!known) return [key, raw];
  const [label, percent] = known;
  const signed = /^[+-]/.test(raw) ? raw : `+${raw}`;
  return [label, statValue(label, percent && !signed.endsWith("%") ? `${signed}%` : signed)];
}

/** A skill's description without the client's placeholders («[%e1.SkillATK_Instant.MinDamage]»): an ellipsis instead. */
export function cleanSkillText(text: string): string {
  return String(text).replace(/\[%[^\]]*\]/g, "…").replace(/…\s*-\s*…/g, "…").replace(/\s{2,}/g, " ").trim();
}
