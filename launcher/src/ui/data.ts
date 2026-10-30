// The program's data for the screens: names and watch items from data/, and a demo chat that stands in for
// Chat.log until Tauri reads the real file.
import itemNamesText from "../../../data/item_names.tsv?raw";
import mapNamesText from "../../../data/map_names.tsv?raw";
import questNamesText from "../../../data/quest_names.tsv?raw";
import watchItemsText from "../../../data/watch_items.csv?raw";
import { parseLinkNames, parseNames, parseWatchItems, isListed, WatchItem } from "../core/items/catalog";

export const itemNames = parseNames(itemNamesText);
export const [mapNames, questNames] = parseLinkNames(mapNamesText, questNamesText);
/** Every item with a description (data/item_specs.json.gz has one for each row of watch_items.csv). */
export const catalog = parseWatchItems(watchItemsText);
/** The «Что искать» list: no white/green items, materials, supplies or misc. */
export const watchItems = catalog.filter(isListed);
export const itemById: Record<string, WatchItem> = Object.fromEntries(watchItems.map((item) => [item.id, item]));
// chat links and item cards: the whole catalog, so stones, scrolls and supplies open too (as Pulse's spec_items)
export const catalogById: Record<string, WatchItem> = Object.fromEntries(catalog.map((item) => [item.id, item]));
export const gradeOf: Record<string, string> = Object.fromEntries(catalog.map((item) => [item.id, item.grade.toLowerCase()]));
export const specByName: Record<string, string> = Object.fromEntries(catalog.map((item) => [item.name, item.id]));

const icons = import.meta.glob("../../../data/icons/*.png", { query: "?url", import: "default", eager: false });

/** URL of an item picture (data/icons/<icon>.png), or null when there is none. */
export async function iconUrl(icon: string): Promise<string | null> {
  const load = icons[`../../../data/icons/${icon}.png`];
  return load ? ((await load()) as string) : null;
}

// ---- demo chat: lines in the Chat.log format, made from real item ids -------------------------------------------
const NICKS = ["Ravenholt", "Valkyra", "Morgrim", "Lunaris", "Galeforce", "Dagon", "Duskmantle", "Nightfox", "Zephyra",
  "Aurelia", "Silverlake", "Wildfire", "Amberleaf", "Hollowkin", "Cragmoor", "Cinderfall", "Sunhaze", "Thornwood"];
const RUDRA = watchItems.filter((item) => /Рудры/.test(item.name));
const link = (id: string) => `[item:${id};ver2;;;]`;
const pick = <T,>(list: T[], n: number) => list[n % list.length];

const TEMPLATES: ((n: number) => string)[] = [
  () => "ищу группу в Дерадикон, ДД 55, есть руны",
  () => "ищу группу в Бездну, нужен хил и чант, 55 лвл",
  (n) => `wts ${link(pick(RUDRA, n).id)}, 2kk, торг в личке`,
  (n) => `продам ${link(pick(RUDRA, n + 3).id)} недорого`,
  () => "ищу группу на осаду, нужен чант",
  (n) => `wts ${link(pick(RUDRA, n).id)} + ${link(pick(RUDRA, n + 1).id)} 3kk`,
  () => "собираю рейд на Инг, 6/12, нужны хилы",
  () => "продам перья и камни, оптом дешевле",
  () => `обменяю ${link("186000163")} x20 на ${link("186000030")}`, // the award medals: green links, Empire cards
  () => "ищу группу на арену хаоса, ДД 54",
];

const pad = (n: number) => String(n).padStart(2, "0");

/** One demo chat line for step n of the demo, stamped with the given time. */
export function demoLine(n: number, at: Date): string {
  const stamp = `${at.getFullYear()}.${pad(at.getMonth() + 1)}.${pad(at.getDate())} ${pad(at.getHours())}:${pad(at.getMinutes())}:${pad(at.getSeconds())}`;
  const nick = pick(NICKS, n * 7 + 3);
  const channel = n % 4 === 3 ? "[1.Общий]" : "[3.Поиск группы]";
  const text = n % 4 === 3 ? pick(["сервер сегодня без лагов", "кто на Инг?", "спасибо за группу"], n) : pick(TEMPLATES, n)(n);
  return `${stamp} : ${channel} [charname:${nick};1.0000 1.0000 1.0000]: ${text} `;
}
