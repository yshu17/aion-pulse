/**
 * A saved build of the gear calculator: class, level and gear sets of item ids with their enchant and stones. Pure.
 *
 *   const saved = readBuild(localStorage.getItem(KEY))   // a broken or missing text gives the default build
 *   writeBuild(saved) -> text
 */

import { KINDS, type SavedConsumables } from "./consumables";
import { isTwoHanded, stoneSlots, type GearItem, type SlotKey } from "./engine";

export interface SavedSlot { id: number; enchant: number; stones: (number | null)[] }
export interface SavedSet {
  title: string; slots: Partial<Record<SlotKey, SavedSlot>>;
  buffs?: (string | number)[]; // skill buffs in use: «class:id» (core/gear/buffs.ts); bare ids in builds saved before
  scrolls?: string[];        // scroll types in use («SpeedRun» …)
  gearTitle?: number | null; // title.id
  consumables?: SavedConsumables; // food, drink, candy in use (core/gear/consumables.ts)
}
export interface SavedBuild { cls: string; level: number; active: number; sets: SavedSet[] }

export const KEY = "pulse.gear.v1";
export const MAX_SETS = 4;

export function emptyBuild(): SavedBuild {
  return { cls: "fighter", level: 55, active: 0, sets: [{ title: "Набор 1", slots: {}, buffs: [], scrolls: [], gearTitle: null, consumables: {} }] };
}

export function readBuild(text: string | null): SavedBuild {
  try {
    const b = JSON.parse(text ?? "") as SavedBuild;
    if (!b || typeof b.cls !== "string" || !Array.isArray(b.sets) || !b.sets.length) return emptyBuild();
    const level = Math.min(Math.max(Math.round(Number(b.level) || 55), 1), 55);
    return { cls: b.cls, level, active: Math.min(Math.max(Number(b.active) || 0, 0), b.sets.length - 1),
      sets: b.sets.slice(0, MAX_SETS).map((s, i) => ({ title: String(s?.title || `Набор ${i + 1}`), slots: s?.slots ?? {},
        buffs: Array.isArray(s?.buffs) ? s.buffs.filter((x) => typeof x === "number" || typeof x === "string") : [], scrolls: Array.isArray(s?.scrolls) ? s.scrolls.map(String) : [],
        gearTitle: typeof s?.gearTitle === "number" ? s.gearTitle : null, consumables: readConsumables(s?.consumables) })) };
  } catch {
    return emptyBuild();
  }
}

/** Only the three kinds with a number for an id. */
function readConsumables(saved: unknown): SavedConsumables {
  const out: SavedConsumables = {};
  for (const [kind] of KINDS) {
    const id = (saved as SavedConsumables | undefined)?.[kind];
    if (typeof id === "number") out[kind] = id;
  }
  return out;
}

export const writeBuild = (b: SavedBuild) => JSON.stringify(b);

/** A copy of the build with one set changed. */
export function withSet(b: SavedBuild, index: number, change: (s: SavedSet) => SavedSet): SavedBuild {
  return { ...b, sets: b.sets.map((s, i) => (i === index ? change(s) : s)) };
}

/** A new set: a copy of the active one (the site does the same), at most MAX_SETS. */
export function addSet(b: SavedBuild): SavedBuild {
  if (b.sets.length >= MAX_SETS) return b;
  const from = b.sets[b.active];
  const copy: SavedSet = { title: `Набор ${b.sets.length + 1}`, slots: JSON.parse(JSON.stringify(from.slots)), buffs: [...(from.buffs ?? [])],
    scrolls: [...(from.scrolls ?? [])], gearTitle: from.gearTitle ?? null, consumables: { ...from.consumables } };
  return { ...b, sets: [...b.sets, copy], active: b.sets.length };
}

export function removeSet(b: SavedBuild, index: number): SavedBuild {
  if (b.sets.length <= 1) return b;
  const sets = b.sets.filter((_, i) => i !== index).map((s, i) => ({ ...s, title: /^Набор \d+$/.test(s.title) ? `Набор ${i + 1}` : s.title }));
  return { ...b, sets, active: Math.min(b.active > index ? b.active - 1 : b.active, sets.length - 1) };
}

/**
 * The main hand and the off hand swapped, each with its enchant and manastones; null when they cannot change places: a weapon
 * that is only for the main hand (a two-hander, a bow) cannot go to the off hand, a shield only to the off hand.
 */
export function swapWeapons(slots: SavedSet["slots"], items: ReadonlyMap<number, GearItem>): SavedSet["slots"] | null {
  const { main, sub } = slots;
  if (!main && !sub) return null;
  const inMain = main && items.get(main.id);
  const inSub = sub && items.get(sub.id);
  if ((main && !inMain) || (sub && !inSub)) return null;
  const toSub = (i: GearItem) => i.grp === "shield" || i.slot === "main_or_sub";
  const toMain = (i: GearItem) => i.grp !== "shield" && (i.slot === "main" || i.slot === "main_or_sub");
  if ((inMain && !toSub(inMain)) || (inSub && !toMain(inSub))) return null;
  const out = { ...slots };
  delete out.main;
  delete out.sub;
  if (sub) out.main = sub;
  if (main) out.sub = main;
  return out;
}

/** The highest manastone level an item takes, from its card's line «Можно усилить магическими камнями 70-го уровня и ниже»; null when the card has none. */
export function stoneCap(blocks: { kind?: string; text?: string }[] | undefined): number | null {
  for (const b of blocks ?? []) {
    const found = b.kind === "text" && b.text ? /камнями\s+(\d+)-го уровня/.exec(b.text) : null;
    if (found) return Number(found[1]);
  }
  return null;
}

/** True when the off hand is not free: the main hand holds a two-hander (a shield or a second weapon cannot go with it). */
export function subBlocked(slots: SavedSet["slots"], items: ReadonlyMap<number, GearItem>): boolean {
  const main = slots.main && items.get(slots.main.id);
  return isTwoHanded(main || undefined);
}

/**
 * The slots with an item put in `slot`, empty enchant and stones (as many places as the item takes).
 * A two-hander in the main hand empties the off hand; the off hand takes nothing while a two-hander is in the main hand (null).
 */
export function putItem(slots: SavedSet["slots"], slot: SlotKey, item: GearItem, items: ReadonlyMap<number, GearItem>): SavedSet["slots"] | null {
  const out = { ...slots };
  if (slot === "sub" && subBlocked(slots, items)) return null;
  out[slot] = { id: item.id, enchant: 0, stones: Array(stoneSlots(item)).fill(null) };
  if (slot === "main" && isTwoHanded(item)) delete out.sub;
  return out;
}
