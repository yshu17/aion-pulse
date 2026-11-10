/**
 * The gear calculator's words: classes, doll slots, item groups and the characteristics as the game names them in Russian,
 * and the four lists the stats panel shows (the same order as aiongear.fun's panel).
 */

import type { SlotKey } from "./engine";

export const CLASSES: [id: string, name: string][] = [
  ["fighter", "Гладиатор"], ["knight", "Страж"], ["assassin", "Убийца"], ["ranger", "Стрелок"],
  ["wizard", "Волшебник"], ["elementalist", "Заклинатель"], ["chanter", "Чародей"], ["cleric", "Целитель"],
];

/** The doll: left column, right column (the order the game's character window has). */
export const DOLL: [SlotKey, string][][] = [
  [["main", "Основное оружие"], ["head", "Голова"], ["shoulder", "Плечи"], ["torso", "Торс"], ["pants", "Ноги"], ["earring1", "Серьга"],
    ["ring1", "Кольцо"], ["necklace", "Ожерелье"]],
  [["sub", "Второе оружие / щит"], ["wing", "Крылья"], ["glove", "Руки"], ["shoes", "Ступни"], ["belt", "Пояс"], ["earring2", "Серьга"],
    ["ring2", "Кольцо"]],
];
export const SLOT_NAME: Record<string, string> = Object.fromEntries(DOLL.flat());

export const GROUP: Record<string, string> = {
  sword: "Меч", greatsword: "Двуручный меч", dagger: "Кинжал", mace: "Булава", polearm: "Копье", staff: "Посох", bow: "Лук",
  spellbook: "Гримуар", orb: "Орб", shield: "Щит", head: "Шлем", earring: "Серьги", ring: "Кольца", necklace: "Ожерелье",
  belt: "Пояс", wing: "Крылья",
};
const ARMOUR: Record<string, string> = { rb: "Ткань", lt: "Кожа", ch: "Кольчуга", pl: "Латы" };
export const groupName = (grp: string) => GROUP[grp] ?? ARMOUR[grp.split("_")[0]] ?? grp;

export const STAT: Record<string, string> = {
  maxhp: "HP", maxmp: "MP", attackrange: "Дальность атаки", attackdelay: "Скор. атаки", boostcastingtime: "Скор. магии",
  speed: "Скорость", flyspeed: "Скор. полёта", maxfp: "Время полёта", boosthate: "Ненависть", concentration: "Концентрация",
  healskillboost: "Сила исцеления", pvpattackratiophysical: "Атака в ПвП", pvpdefendratiophysical: "Защита в ПвП",
  r_damage: "[П] Атака", r_hitaccuracy: "[П] Точность", r_critical: "[П] Ф. крит.", l_damage: "[Л] Атака", l_hitaccuracy: "[Л] Точность",
  l_critical: "[Л] Ф. крит.", magicalskillboost: "Сила магии", magicalhitaccuracy: "Точн. маг.", magicalcritical: "Маг. крит.",
  str: "Сила", vit: "Здоровье", acc: "Точность", agi: "Ловкость", int: "Знание", wis: "Воля",
  physicaldefend: "Физ. защита", block: "Блок щитом", damagereduce: "Снижение урона", reducemax: "Предел снижения", parry: "Парирование",
  dodge: "Уклонение", physicalcriticalreducerate: "Сопр. физ. крит.", physicalcriticaldamagereduce: "Сниж. физ. крит. урона",
  magicalresist: "Маг. защита", magicalcriticalreducerate: "Сопр. маг. крит.", magicalcriticaldamagereduce: "Сниж. маг. крит. урона",
  elementaldefendfire: "Защита от огня", elementaldefendearth: "Защита от земли", elementaldefendair: "Защита от ветра",
  elementaldefendwater: "Защита от воды",
  // item and stone lines
  phyattack: "Физ. атака", magicalattack: "Маг. атака", hitaccuracy: "Точность", critical: "Ф. крит.", pvpattackratio: "Атака в ПвП",
  pvpdefendratio: "Защита в ПвП", maxFp: "Время полёта", mindamage: "Мин. урон", maxdamage: "Макс. урон", magicalaccuracy: "Точн. маг.",
  hitcount: "Ударов", arparalyze: "Сопр. параличу", arsilence: "Сопр. немоте",
};
export const statName = (stat: string) => STAT[stat] ?? stat;

/** The panel's lists, as the site groups them. */
export const PANEL: { title: string; stats: string[] }[] = [
  { title: "Основное", stats: ["maxhp", "maxmp", "attackrange", "attackdelay", "boostcastingtime", "speed", "flyspeed", "maxfp", "boosthate",
    "concentration", "healskillboost", "pvpattackratiophysical", "pvpdefendratiophysical"] },
  { title: "Атака", stats: ["r_damage", "r_hitaccuracy", "r_critical", "l_damage", "l_hitaccuracy", "l_critical", "magicalskillboost",
    "magicalhitaccuracy", "magicalcritical", "str", "vit", "acc", "agi", "int", "wis"] },
  { title: "Защита", stats: ["physicaldefend", "block", "damagereduce", "reducemax", "parry", "dodge", "physicalcriticalreducerate",
    "physicalcriticaldamagereduce", "magicalresist", "magicalcriticalreducerate", "magicalcriticaldamagereduce", "elementaldefendfire",
    "elementaldefendearth", "elementaldefendair", "elementaldefendwater"] },
];
