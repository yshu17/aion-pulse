/**
 * Resets (the daily and weekly «откаты» of the server): the ones of data/schedule.json, what the user changed in them,
 * the ones the user hid, and the user's own. File `schedule_resets.json` next to config.json:
 *
 *     {"edits": {"r0": {"name": "Откат", "days": ["mon", "thu"], "time": "08:30"}},
 *      "removed": ["r2"],
 *      "own": [{"id": "own1", "name": "Рейд", "days": ["fri"], "time": "20:00"}]}
 *
 * A reset repeats on `days` (all seven = every day) at `time`, server time (MSK).
 * - `parseResets(text)` / `serializeResets(store)` — a missing or broken file means no changes; the first format of
 *   26.10 (`when`/`day`) is read too;
 * - `resolveResets(base, store)` — every shown reset with its id, the changes applied, `own` and `edited` marks;
 * - `saveReset`, `removeReset`, `restoreResets` — the store after a change (pure: data in, data out);
 * - `resetBellKey(id)` — the id under which the bell and the lead of a reset are kept (with the bells of events);
 * - `resetEvents(reset)` — the weekly occurrences the reminder planner understands;
 * - `checkReset(draft)` — "" when valid, else what to fix (Russian, for the form);
 * - `daysText(days)` — «Каждый день», «Ср», «Пн, Чт».
 */

import { DAYS, ScheduleEvent } from "./reminders";

/** A reset as data/schedule.json has it. */
export interface BaseReset {
  name: string;
  when: string;
  day?: string;
  time: string;
}

export interface ResetDraft {
  name: string;
  days: string[];
  time: string;
}

export interface Reset extends ResetDraft {
  id: string;
  own: boolean;
  edited: boolean; // a reset of the server the user changed
}

export interface ResetStore {
  edits: Record<string, ResetDraft>;
  removed: string[];
  own: (ResetDraft & { id: string })[];
}

export const EMPTY_RESETS: ResetStore = { edits: {}, removed: [], own: [] };
export const RESETS_FILE = "schedule_resets.json";
const SHORT: Record<string, string> = { mon: "Пн", tue: "Вт", wed: "Ср", thu: "Чт", fri: "Пт", sat: "Сб", sun: "Вс" };

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;
const isDict = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
export const resetBellKey = (id: string) => `reset:${id}`;
export const baseId = (index: number) => `r${index}`;
const ordered = (days: string[]) => DAYS.filter((d) => days.includes(d));

export function checkReset(draft: ResetDraft): string {
  if (!draft.name.trim()) return "Укажи название отката.";
  if (!draft.days.some((d) => DAYS.includes(d))) return "Выбери хотя бы один день.";
  if (!TIME.test(draft.time)) return "Укажи время как ЧЧ:ММ, например 09:00.";
  return "";
}

export function daysText(days: string[]): string {
  const list = ordered(days);
  return list.length === 7 ? "Каждый день" : list.map((d) => SHORT[d]).join(", ");
}

/** The days of a base reset or of a saved entry: `days`, else the old `when`/`day`. */
function daysOf(raw: Record<string, unknown>): string[] {
  if (Array.isArray(raw.days)) return ordered(raw.days.filter((d): d is string => typeof d === "string"));
  if (raw.when === "daily") return [...DAYS];
  return typeof raw.day === "string" && DAYS.includes(raw.day) ? [raw.day] : [];
}

/** A saved draft, or null when it is broken. A missing name or days come from `fallback` (old edits kept only the time). */
function readDraft(raw: unknown, fallback?: ResetDraft): ResetDraft | null {
  if (!isDict(raw)) return null;
  const days = daysOf(raw);
  const draft = {
    name: typeof raw.name === "string" ? raw.name.trim() : fallback?.name ?? "",
    days: days.length ? days : fallback?.days ?? [],
    time: typeof raw.time === "string" ? raw.time : "",
  };
  return checkReset(draft) ? null : draft;
}

export function parseResets(text: string | null, base: BaseReset[] = []): ResetStore {
  try {
    const data = text ? JSON.parse(text) : null;
    if (!isDict(data)) return EMPTY_RESETS;
    const edits: Record<string, ResetDraft> = {};
    if (isDict(data.edits)) {
      for (const [id, raw] of Object.entries(data.edits)) {
        const original = base[Number(id.slice(1))];
        const draft = readDraft(raw, original && fromBase(original));
        if (draft) edits[id] = draft;
      }
    }
    const removed = Array.isArray(data.removed) ? data.removed.filter((id): id is string => typeof id === "string") : [];
    const own: ResetStore["own"] = [];
    if (Array.isArray(data.own)) {
      for (const raw of data.own) {
        const draft = readDraft(raw);
        if (draft && isDict(raw) && typeof raw.id === "string") own.push({ id: raw.id, ...draft });
      }
    }
    return { edits, removed, own };
  } catch {
    return EMPTY_RESETS;
  }
}

export const serializeResets = (store: ResetStore): string => JSON.stringify(store, null, 1) + "\n";

export const fromBase = (r: BaseReset): ResetDraft => ({ name: r.name, days: daysOf(r as unknown as Record<string, unknown>), time: r.time });

const same = (a: ResetDraft, b: ResetDraft) => a.name === b.name && a.time === b.time && ordered(a.days).join() === ordered(b.days).join();

export function resolveResets(base: BaseReset[], store: ResetStore): Reset[] {
  const out: Reset[] = [];
  base.forEach((r, i) => {
    const id = baseId(i);
    if (store.removed.includes(id)) return;
    const edit = store.edits[id];
    out.push({ id, ...(edit ?? fromBase(r)), own: false, edited: edit !== undefined });
  });
  for (const r of store.own) out.push({ ...r, own: true, edited: false });
  return out;
}

/** Save a draft: a new own reset (id null), a changed own one, or a changed server one (its original drops the edit). */
export function saveReset(base: BaseReset[], store: ResetStore, id: string | null, draft: ResetDraft): ResetStore {
  const clean = { name: draft.name.trim(), days: ordered(draft.days), time: draft.time };
  if (id === null) return { ...store, own: [...store.own, { id: nextOwnId(store), ...clean }] };
  if (store.own.some((r) => r.id === id)) return { ...store, own: store.own.map((r) => (r.id === id ? { id, ...clean } : r)) };
  const edits = { ...store.edits };
  const original = base[Number(id.slice(1))];
  if (original && same(fromBase(original), clean)) delete edits[id];
  else edits[id] = clean;
  return { ...store, edits };
}

/** An own reset is deleted; a server one is hidden (and comes back with `restoreResets`). */
export function removeReset(store: ResetStore, id: string): ResetStore {
  if (store.own.some((r) => r.id === id)) return { ...store, own: store.own.filter((r) => r.id !== id) };
  return { ...store, removed: [...store.removed.filter((x) => x !== id), id] };
}

export const restoreResets = (store: ResetStore): ResetStore => ({ ...store, removed: [] });

/** The occurrences of a reset in the week, one per day; each is a one-minute event. */
export function resetEvents(reset: ResetDraft): ScheduleEvent[] {
  const [h, m] = reset.time.split(":").map(Number);
  const end = h * 60 + m + 1;
  const stop = end >= 1440 ? "24:00" : `${String(Math.floor(end / 60)).padStart(2, "0")}:${String(end % 60).padStart(2, "0")}`;
  return ordered(reset.days).map((day) => ({ day, start: reset.time, end: stop, name: reset.name, kind: "Откат" }));
}

export function nextOwnId(store: ResetStore): string {
  const used = store.own.map((r) => Number(r.id.replace(/\D/g, "")) || 0);
  return `own${Math.max(0, ...used) + 1}`;
}
