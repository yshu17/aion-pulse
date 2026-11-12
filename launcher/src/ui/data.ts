// The program's data for the screens: the items and quests from the game database (pulse.db, core/db/items.ts and
// game.ts), map names from data/, and a demo chat that stands in for Chat.log until Tauri reads the real file.
import { useEffect, useState } from "react";

import mapNamesText from "../../../data/map_names.tsv?raw";
import { questNames as readQuestNames } from "../core/db/game";
import { itemCatalog } from "../core/db/items";
import { parseNames, isListed, WatchItem } from "../core/items/catalog";
import { pulseDb } from "./db/pulseDb";

export const mapNames = parseNames(mapNamesText);

// The item and quest data: empty until loadItems() has read the database (the windows wait for it, useItems). The
// bindings are live: a screen that reads them after the load sees the database's data.
export let questNames: Record<string, string> = {};
export let itemNames: Record<string, string> = {};
/** Every item with a card (a description). */
export let catalog: WatchItem[] = [];
/** The «Что искать» list: no white/green items, materials, supplies or misc. */
export let watchItems: WatchItem[] = [];
export let itemById: Record<string, WatchItem> = {};
// chat links and item cards: the whole catalog, so stones, scrolls and supplies open too (as Pulse's spec_items)
export let catalogById: Record<string, WatchItem> = {};
export let gradeOf: Record<string, string> = {};
export let specByName: Record<string, string> = {};

let loading: Promise<string> | null = null;

/** Reads the items from pulse.db once; the answer is "" or what went wrong (the data then stays empty). */
export function loadItems(): Promise<string> {
  loading ??= (async () => {
    const all = await pulseDb();
    if (!all) return "Нет базы игры data/pulse.db: предметы не загружены.";
    const [items, quests] = await Promise.all([itemCatalog(all), readQuestNames(all)]);
    questNames = quests;
    itemNames = items.names;
    catalog = items.catalog;
    watchItems = catalog.filter(isListed);
    itemById = Object.fromEntries(watchItems.map((item) => [item.id, item]));
    catalogById = Object.fromEntries(catalog.map((item) => [item.id, item]));
    gradeOf = Object.fromEntries(catalog.map((item) => [item.id, item.grade.toLowerCase()]));
    specByName = Object.fromEntries(catalog.map((item) => [item.name, item.id]));
    return "";
  })().catch((error) => `Не удалось прочитать предметы из базы игры: ${error}`);
  return loading;
}

/** The item data for a window: ready once loaded; `problem` says what went wrong ("" when all is well). */
export function useItems(): { ready: boolean; problem: string } {
  const [state, setState] = useState({ ready: false, problem: "" });
  useEffect(() => {
    let live = true;
    loadItems().then((problem) => live && setState({ ready: true, problem }));
    return () => { live = false; };
  }, []);
  return state;
}

// items at the top, the skills' and pets' pictures in skills/ and pets/ (tools/sync_catalog_icons.py)
// the addresses of all of them are one small module (./iconMap), asked for once: a request per picture made every list flicker
let iconMap: Record<string, string> | null = null;
let iconsLoading: Promise<Record<string, string>> | null = null;
const loadIcons = () => (iconsLoading ??= import("./iconMap").then((m) => (iconMap = m.ICONS)));

/** URL of a picture (data/icons/<icon>.png, «skills/…» and «pets/…» too), or null when there is none. */
export async function iconUrl(icon: string): Promise<string | null> {
  return (await loadIcons())[`../../../data/icons/${icon}.png`] ?? null;
}

/** The same at once, when the addresses are already here: undefined while they are still coming. */
export function iconUrlNow(icon: string): string | null | undefined {
  return iconMap ? iconMap[`../../../data/icons/${icon}.png`] ?? null : undefined;
}

// ---- demo chat: lines in the Chat.log format, made from real item ids -------------------------------------------
const NICKS = ["Ravenholt", "Valkyra", "Morgrim", "Lunaris", "Galeforce", "Dagon", "Duskmantle", "Nightfox", "Zephyra",
  "Aurelia", "Silverlake", "Wildfire", "Amberleaf", "Hollowkin", "Cragmoor", "Cinderfall", "Sunhaze", "Thornwood"];
let rudra: WatchItem[] = [];
const RUDRA_ITEM = { id: "110600968" } as WatchItem; // without the database: one link all the same
const link = (id: string) => `[item:${id};ver2;;;]`;
const pick = <T,>(list: T[], n: number) => list[n % list.length];
const pickRudra = (n: number) => {
  if (!rudra.length) rudra = watchItems.filter((item) => /Рудры/.test(item.name));
  return rudra.length ? pick(rudra, n) : RUDRA_ITEM;
};

const TEMPLATES: ((n: number) => string)[] = [
  () => "ищу группу в Дерадикон, ДД 55, есть руны",
  () => "ищу группу в Бездну, нужен хил и чант, 55 лвл",
  (n) => `wts ${link(pickRudra(n).id)}, 2kk, торг в личке`,
  (n) => `продам ${link(pickRudra(n + 3).id)} недорого`,
  () => "ищу группу на осаду, нужен чант",
  (n) => `wts ${link(pickRudra(n).id)} + ${link(pickRudra(n + 1).id)} 3kk`,
  () => "собираю рейд на Инг, 6/12, нужны хилы",
  () => "продам перья и камни, оптом дешевле",
  () => `обменяю ${link("186000163")} x20 на ${link("186000030")}`, // the award medals: green links, Empire cards
  () => "собираемся у [pos:Место;0 220070000 1870.0 2840.0 0.0], идём на крепость", // a place link: opens the map
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
