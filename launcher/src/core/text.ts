/** Small Russian text helpers shared by the core groups — the port of core/text.py. */

import { pyFixed, pyRound } from "./py";

/** «1 слово», «3 слова», «5 слов» (Russian plural forms). */
export function plural(n: number, one: string, few: string, many: string): string {
  const last2 = n % 100;
  const last = n % 10;
  const word = last === 1 && last2 !== 11 ? one : last >= 2 && last <= 4 && !(last2 >= 12 && last2 <= 14) ? few : many;
  return `${n} ${word}`;
}

/** «хил, ММК ,,чант» -> ["хил", "ММК", "чант"]. */
export function splitKeywords(text: string): string[] {
  return text.split(",").map((part) => part.trim()).filter((part) => part !== "");
}

/** «384 м», «1.6 км» (rounded as Python rounds: a tie goes to the even digit). */
export function metresText(metres: number): string {
  return metres < 1000 ? `${pyRound(metres)} м` : `${pyFixed(metres / 1000, 1)} км`;
}
