/** The stigma calculator's build in this computer's storage: class, faction, level and the pick; anything odd falls back to the default. */

import { emptyPick, MAX_LEVEL, MIN_LEVEL, type Faction, type Pick } from "./calc";

export const KEY = "pulse.stigma.v1";
const CLASSES = ["fighter", "knight", "assassin", "ranger", "wizard", "elementalist", "chanter", "cleric"];

export interface Saved { cls: string; faction: Faction; level: number; pick: Pick }

export const defaultSaved = (): Saved => ({ cls: "fighter", faction: "elyos", level: MAX_LEVEL, pick: emptyPick() });

const ids = (v: unknown): string[] => (Array.isArray(v) && v.every((x) => typeof x === "string") ? v : []);

export function readSaved(text: string | null): Saved {
  const out = defaultSaved();
  let raw: Record<string, any>;
  try { raw = JSON.parse(text ?? ""); } catch { return out; }
  if (!raw || typeof raw !== "object") return out;
  if (CLASSES.includes(raw.cls)) out.cls = raw.cls;
  if (raw.faction === "elyos" || raw.faction === "asmodian") out.faction = raw.faction;
  if (Number.isFinite(raw.level)) out.level = Math.min(Math.max(Math.round(raw.level), MIN_LEVEL), MAX_LEVEL);
  const p = raw.pick && typeof raw.pick === "object" ? raw.pick : {};
  const levels = p.levels && typeof p.levels === "object"
    ? Object.fromEntries(Object.entries(p.levels).filter(([, v]) => Number.isFinite(v))) as Record<string, number> : {};
  out.pick = { normal: ids(p.normal), advanced: ids(p.advanced), levels };
  return out;
}

export const writeSaved = (saved: Saved) => JSON.stringify(saved);
