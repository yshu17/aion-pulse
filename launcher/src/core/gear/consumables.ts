/**
 * «Расходники» of the gear calculator's «Усиление»: food, drinks and the stat candies. Pure.
 * The data is data/consumables/consumables.json (tools/build_consumables.py); one of each kind is in use at a time.
 * The numbers are the item card's own: see the note the screen shows.
 *
 *   chosenConsumables(saved, table) -> Consumable[]  saved: {food?: id, drink?: id, candy?: id}; any of an entry's ids finds it
 *   putConsumable(saved, kind, id | null) -> saved
 *   consumableLines(list) -> Line[]                  [engine stat, value, percent] for calcStats
 *   consumableTotals(list) -> [stat name, sum, percent][]
 *   filterConsumables(table, {kind, stat, query, noEvent, same}) -> {rows: [{item, more}], stats: [name, items][], stat, total, matched}
 */
import type { Line } from "./engine";

export type ConsumableKind = "food" | "drink" | "candy";
export type ConsumableStat = [name: string, value: number, percent: boolean];
export interface Consumable {
  id: number; ids: number[]; name: string; kind: ConsumableKind; grade: string; icon: string;
  item_level: number; use_level: number | null; minutes: number; stats: ConsumableStat[]; unknown: string[];
}
export type SavedConsumables = Partial<Record<ConsumableKind, number>>;

export const KINDS: [ConsumableKind, string][] = [["food", "Еда"], ["drink", "Напиток"], ["candy", "Конфета"]];

/** The engine's key for each stat name of the data. */
export const STAT_KEY: Record<string, string> = {
  "Физ. атака": "phyattack", "Сила магии": "magicalskillboost", "Макс. HP": "maxhp", "Макс. MP": "maxmp", "Точность": "hitaccuracy",
  "Маг. точность": "magicalhitaccuracy", "Уклонение": "dodge", "Маг. защита": "magicalresist", "Физ. крит.": "critical",
  "Защ. от стихий": "elementaldefendall", "Скорость": "speed", "Скорость атаки": "attackdelay", "Скорость магии": "boostcastingtime",
  "Восст. HP": "hpregen", "Восст. MP": "mpregen",
};

export function chosenConsumables(saved: SavedConsumables | undefined, table: Consumable[]): Consumable[] {
  return KINDS.map(([kind]) => {
    const id = saved?.[kind];
    return id === undefined ? undefined : table.find((x) => x.kind === kind && x.ids.includes(id));
  }).filter((x): x is Consumable => !!x);
}

export function putConsumable(saved: SavedConsumables | undefined, kind: ConsumableKind, id: number | null): SavedConsumables {
  const out = { ...saved };
  if (id === null) delete out[kind];
  else out[kind] = id;
  return out;
}

export const consumableLines = (list: Consumable[]): Line[] =>
  list.flatMap((x) => x.stats.filter(([name]) => STAT_KEY[name]).map(([name, value, percent]): Line => [STAT_KEY[name], value, percent]));

export function consumableTotals(list: Consumable[]): ConsumableStat[] {
  const out = new Map<string, ConsumableStat>();
  for (const x of list) for (const [name, value, percent] of x.stats) {
    const key = `${name}|${percent}`;
    out.set(key, [name, (out.get(key)?.[1] ?? 0) + value, percent]);
  }
  return [...out.values()];
}

export const statText = ([name, value, percent]: ConsumableStat) => `${name} +${value}${percent ? "%" : ""}`;
export const effectText = (x: Consumable) => x.stats.map(statText).join(", ");
/** The bonuses the client gives no number for: named, never counted. */
export const unknownText = (x: Consumable) => (x.unknown.length ? `${x.unknown.join(", ")}: значение неизвестно` : "");
export const timeText = (minutes: number) => (minutes % 60 === 0 ? `${minutes / 60} ч` : `${minutes} мин`);

export interface ConsumableFilter { kind: ConsumableKind; stat: string; query: string; noEvent: boolean; same: boolean }
export interface ConsumableRow { item: Consumable; more: number } // more: others with the same effect, folded into this row

const plain = (text: string) => text.toLowerCase().replace(/ё/g, "е");

export function filterConsumables(table: Consumable[], f: ConsumableFilter) {
  const kind = table.filter((x) => x.kind === f.kind && (!f.noEvent || !x.name.startsWith("[Ивент]")));
  const counts = new Map<string, number>();
  for (const x of kind) for (const name of new Set(x.stats.map((s) => s[0]))) counts.set(name, (counts.get(name) ?? 0) + 1);
  const stats = [...counts].sort((a, b) => b[1] - a[1]);
  const stat = counts.has(f.stat) ? f.stat : "";
  const query = plain(f.query.trim());
  const value = (x: Consumable) => Math.max(0, ...x.stats.filter((s) => s[0] === stat).map((s) => s[1]));
  const found = kind.filter((x) => (!stat || x.stats.some((s) => s[0] === stat)) && (!query || plain(x.name).includes(query)))
    .sort((a, b) => (stat ? value(b) - value(a) : 0) || Number(a.name.startsWith("[")) - Number(b.name.startsWith("["))
      || b.minutes - a.minutes || a.name.localeCompare(b.name, "ru"));
  let rows: ConsumableRow[] = found.map((item) => ({ item, more: 0 }));
  if (f.same) {
    const by = new Map<string, ConsumableRow>();
    for (const item of found) {
      const key = `${item.minutes}|${effectText(item)}|${unknownText(item)}`;
      const at = by.get(key);
      if (at) at.more++;
      else by.set(key, { item, more: 0 });
    }
    rows = [...by.values()];
  }
  return { rows, stats, stat, total: kind.length, matched: found.length };
}
