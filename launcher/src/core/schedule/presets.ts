/**
 * Schedule presets: up to four named sets of the user's schedule, like the gear calculator's «Набор 1, Набор 2…».
 * File `schedule_presets.json` next to config.json:
 *
 *     {"active": 0, "presets": [{"title": "Набор 1", "state": null}, {"title": "Твинк", "state": {...}}]}
 *
 * A set's state is everything the user changes in «Расписание»: own and hidden events (schedule_custom.json), the
 * reminders (config remind_events) with their own leads (schedule_leads.json), the hidden filters (config
 * schedule_hidden), the changed, hidden and own resets (schedule_resets.json) and the link the schedule is checked by
 * (schedule_source.json; a set may have none). Those files stay the working copy of
 * the active set: switching keeps the working copy in the set left and gives the chosen set's state to load. The active
 * set's stored state may be older than the working copy (null at first): it is written on the next switch.
 *
 *   readPresets(text) / writePresets(store)          the file; anything odd falls back to one empty set
 *   addPreset(store, now)                            a copy of the schedule now, at most MAX_PRESETS, made active
 *   switchPreset(store, index, now) -> {store, load} load: the chosen set's state, null when it is the active one
 *   removePreset(store, index, now) -> {store, load} load: the neighbour's state when the active set goes, else null
 *   renamePreset(store, index, title)                a trimmed name of up to 24 letters; an empty one is refused
 */

import type { CustomData } from "./scheduleCustom";
import type { ResetStore } from "./resets";

export interface ScheduleState {
  custom: CustomData;
  remind: string[];
  leads: Record<string, number>;
  hidden: string[];
  resets: ResetStore;
  /** The set's own schedule link (schedule_source.json); url "" — the set has none. Missing in files of before. */
  source?: { url: string; known: string | null };
}

export interface Preset { title: string; state: ScheduleState | null }
export interface PresetStore { active: number; presets: Preset[] }

export const MAX_PRESETS = 4;
export const PRESETS_FILE = "schedule_presets.json";
const TITLE_MAX = 24;
const DEFAULT_TITLE = /^Набор \d+$/;

export const emptyState = (): ScheduleState => ({ custom: { added: [], removed: [] }, remind: [], leads: {}, hidden: [], resets: { edits: {}, removed: [], own: [] } });

const isDict = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === "string");
const copy = <T>(v: T): T => JSON.parse(JSON.stringify(v));

/** A stored state when its shape is right (the files' own readers check the details when it is loaded), else null. */
function readState(raw: unknown): ScheduleState | null {
  if (!isDict(raw)) return null;
  const { custom, remind, leads, hidden, resets, source } = raw;
  if (!isDict(custom) || !Array.isArray(custom.added) || !custom.added.every(isDict) || !strings(custom.removed)) return null;
  if (!strings(remind) || !strings(hidden) || !isDict(leads) || !Object.values(leads).every((n) => Number.isInteger(n) && (n as number) > 0)) return null;
  if (!isDict(resets) || !isDict(resets.edits) || !strings(resets.removed) || !Array.isArray(resets.own)) return null;
  const link = isDict(source) && typeof source.url === "string" && (source.known === null || typeof source.known === "string") ? { url: source.url, known: source.known } : undefined;
  return copy({ custom, remind, leads, hidden, resets, ...(link ? { source: link } : {}) }) as unknown as ScheduleState;
}

export function readPresets(text: string | null): PresetStore {
  const fresh: PresetStore = { active: 0, presets: [{ title: "Набор 1", state: null }] };
  let raw: unknown;
  try { raw = text ? JSON.parse(text) : null; } catch { return fresh; }
  if (!isDict(raw) || !Array.isArray(raw.presets)) return fresh;
  const presets = raw.presets.filter(isDict).slice(0, MAX_PRESETS).map((p, i): Preset => ({
    title: typeof p.title === "string" && p.title.trim() ? p.title.trim().slice(0, TITLE_MAX) : `Набор ${i + 1}`,
    state: readState(p.state),
  }));
  if (!presets.length) return fresh;
  const active = Number.isInteger(raw.active) ? Math.min(Math.max(raw.active as number, 0), presets.length - 1) : 0;
  return { active, presets };
}

export const writePresets = (store: PresetStore) => JSON.stringify(store, null, 1) + "\n";

/** The store with the schedule now kept in the active set. */
const keep = (store: PresetStore, now: ScheduleState): Preset[] =>
  store.presets.map((p, i) => (i === store.active ? { ...p, state: copy(now) } : p));

export function addPreset(store: PresetStore, now: ScheduleState): PresetStore {
  if (store.presets.length >= MAX_PRESETS) return store;
  const presets = [...keep(store, now), { title: `Набор ${store.presets.length + 1}`, state: copy(now) }];
  return { active: presets.length - 1, presets };
}

export function switchPreset(store: PresetStore, index: number, now: ScheduleState): { store: PresetStore; load: ScheduleState | null } {
  if (index === store.active || !store.presets[index]) return { store, load: null };
  const presets = keep(store, now);
  return { store: { active: index, presets }, load: copy(presets[index].state ?? emptyState()) };
}

export function removePreset(store: PresetStore, index: number, now: ScheduleState): { store: PresetStore; load: ScheduleState | null } {
  if (store.presets.length <= 1 || !store.presets[index]) return { store, load: null };
  const presets = keep(store, now).filter((_, i) => i !== index)
    .map((p, i) => ({ ...p, title: DEFAULT_TITLE.test(p.title) ? `Набор ${i + 1}` : p.title }));
  if (index !== store.active) return { store: { active: store.active > index ? store.active - 1 : store.active, presets }, load: null };
  const active = Math.min(index, presets.length - 1);
  return { store: { active, presets }, load: copy(presets[active].state ?? emptyState()) };
}

export function renamePreset(store: PresetStore, index: number, title: string): PresetStore {
  const name = title.trim().slice(0, TITLE_MAX);
  if (!name || !store.presets[index]) return store;
  return { ...store, presets: store.presets.map((p, i) => (i === index ? { ...p, title: name } : p)) };
}
