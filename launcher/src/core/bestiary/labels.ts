/**
 * Stable, localized bestiary categories shared by indexing and presentation — the port of
 * core/bestiary/bestiary_labels.py.
 *
 * Known difference: Python's \d in statText also takes non-ASCII digits; here only 0–9 are grouped.
 */

import { casefold, pyStr } from "../py";

export { plural } from "../text"; // one Russian plural for every group

/** Group large numeric values without changing labels or rank numbers: «1234567» -> «1 234 567». */
export function statText(value: unknown): string {
  return pyStr(value).replace(/\d{4,}/g, (digits) => BigInt(digits).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " "));
}

export const FACTIONS = ["Элийцы", "Асмодиане", "Балауры", "Другие"];

export const RACES: Record<string, string> = {
  pc_light: "Элиец", pc_dark: "Асмодианин", drakan: "Балаур",
  dragon: "Балаур", naga: "Нага", beast: "Зверь",
  demihumanoid: "Полугуманоид", humanoid: "Гуманоид", undead: "Нежить",
  magicalmonster: "Магическое существо", lizardman: "Ящер",
  brownie: "Брауни", construct: "Конструкт", shulack: "Шурак",
  krall: "Кралл", elemental: "Элементаль", lycan: "Ликан",
  ratman: "Ратман", goblin: "Гоблин", npc: "NPC",
  teleporter: "Привратник", barrier: "Барьер", carrier: "Перевозчик",
  outsider: "Иное существо", livingwater: "Живая вода", neut: "Нейтральный",
  aggressivesinglemonster: "Монстр",
};

const startsWithAny = (value: string, prefixes: string[]) => prefixes.some((p) => value.startsWith(p));

/** Group client codes case-insensitively; do not infer allegiance from a name. */
export function factionFor(rawRace: string, displayRace = ""): string {
  const value = casefold(rawRace.trim());
  const display = casefold(displayRace.trim());
  if (startsWithAny(value, ["pc_light", "gchief_light", "ghenchman_light"]) || ["элиец", "элийцы", "elyos"].includes(display)) {
    return "Элийцы";
  }
  if (startsWithAny(value, ["pc_dark", "gchief_dark", "ghenchman_dark"]) || ["асмодианин", "асмодиане", "asmodian"].includes(display)) {
    return "Асмодиане";
  }
  if (["drakan", "dragon", "naga"].includes(value) || value.startsWith("dragon_castle")
      || ["балаур", "балауры", "balaur"].includes(display)) {
    return "Балауры";
  }
  return "Другие";
}

export function raceLabel(rawRace: string, displayRace = ""): string {
  if (displayRace && [...displayRace].some((c) => "а" <= casefold(c) && casefold(c) <= "я")) return displayRace.trim();
  const value = casefold((displayRace || rawRace).trim());
  if (Object.prototype.hasOwnProperty.call(RACES, value)) return RACES[value];
  const group = factionFor(rawRace, displayRace);
  return group !== "Другие" ? group : "Другое существо";
}
