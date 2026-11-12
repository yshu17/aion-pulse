/**
 * A saved build of the gear calculator: class, level and gear sets of item ids with their enchant and stones. Pure.
 *
 *   const saved = readBuild(localStorage.getItem(KEY))   // a broken or missing text gives the default build
 *   writeBuild(saved) -> text
 */

import type { GearItem, SlotKey } from "./engine";

export interface SavedSlot { id: number; enchant: number; stones: (number | null)[] }
export interface SavedSet {
  title: string; slots: Partial<Record<SlotKey, SavedSlot>>;
  buffs?: number[];          // active skills in use (ids)
  scrolls?: string[];        // scroll types in use («SpeedRun» …)
  gearTitle?: number | null; // title.id
}
export interface SavedBuild { cls: string; level: number; active: number; sets: SavedSet[] }

export const KEY = "pulse.gear.v1";
export const MAX_SETS = 4;

export function emptyBuild(): SavedBuild {
  return { cls: "fighter", level: 55, active: 0, sets: [{ title: "Набор 1", slots: {}, buffs: [], scrolls: [], gearTitle: null }] };
}

export function readBuild(text: string | null): SavedBuild {
  try {
    const b = JSON.parse(text ?? "") as SavedBuild;
    if (!b || typeof b.cls !== "string" || !Array.isArray(b.sets) || !b.sets.length) return emptyBuild();
    const level = Math.min(Math.max(Math.round(Number(b.level) || 55), 1), 55);
    return { cls: b.cls, level, active: Math.min(Math.max(Number(b.active) || 0, 0), b.sets.length - 1),
      sets: b.sets.slice(0, MAX_SETS).map((s, i) => ({ title: String(s?.title || `Набор ${i + 1}`), slots: s?.slots ?? {},
        buffs: Array.isArray(s?.buffs) ? s.buffs.map(Number) : [], scrolls: Array.isArray(s?.scrolls) ? s.scrolls.map(String) : [],
        gearTitle: typeof s?.gearTitle === "number" ? s.gearTitle : null })) };
  } catch {
    return emptyBuild();
  }
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
    scrolls: [...(from.scrolls ?? [])], gearTitle: from.gearTitle ?? null };
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
