/**
 * The gear calculator's titles as «База данных» shows them. Pure.
 *
 *   titleSide("pc_light,pc_dark") -> "Обе стороны" | "Элийцы" | "Асмодиане" | ""
 *   titleSummary(["maxHp 20"]) -> "Макс. HP +20"            the bonuses in the game's words, not the client's keys
 *   findTitles(titles, "крит", limit?) -> the titles whose name or bonuses say it (any case, «ё» as «е»)
 */
import { bonusLine } from "../items/statNames";

export interface GearTitle { id: number; name: string; race: string; bonus: string[]; icon: string }

export function titleSide(race: string): string {
  const light = race.includes("pc_light"), dark = race.includes("pc_dark");
  return light && dark ? "Обе стороны" : light ? "Элийцы" : dark ? "Асмодиане" : "";
}

export function titleSummary(bonus: string[]): string {
  return bonus.map((b) => bonusLine(b).join(" ")).join(", ");
}

const fold = (t: string) => t.toLowerCase().split("ё").join("е");

export function findTitles<T extends GearTitle>(titles: T[], query: string, limit = 80): T[] {
  const q = fold(query.trim());
  const found = q ? titles.filter((t) => fold(`${t.name} ${titleSummary(t.bonus)}`).includes(q)) : titles;
  return found.slice(0, limit);
}
