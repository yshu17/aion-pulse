/**
 * A saved build of the gear calculator: class, level and gear sets of item ids with their enchant and stones. Pure.
 *
 *   const saved = readBuild(localStorage.getItem(KEY))   // a broken or missing text gives the default build
 *   writeBuild(saved) -> text
 */

import type { SlotKey } from "./engine";

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
