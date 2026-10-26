/**
 * Resets (the daily and weekly «откаты» of the server): the ones of data/schedule.json, the time the user changed, and
 * the user's own. File `schedule_resets.json` next to config.json:
 *
 *     {"edits": {"r0": {"time": "08:30", "day": "thu"}}, "own": [{"id": "own1", "name": "Рейд", "when": "weekly", "day": "fri", "time": "20:00"}]}
 *
 * - `parseResets(text)` / `serializeResets(store)` — a missing or broken file means no changes;
 * - `resolveResets(base, store)` — every reset with its id, the changed time applied, `own` and `edited` marks;
 * - `resetBellKey(id)` — the id under which the bell and the lead of a reset are kept (with the bells of events);
 * - `resetEvents(reset)` — the weekly occurrences (one per day for a daily reset) the reminder planner understands;
 * - `checkReset(draft)` — "" when valid, else what to fix (Russian, for the form).
 * Times are server time (MSK).
 */

import { DAYS, ScheduleEvent } from "./reminders";

export type ResetWhen = "daily" | "weekly";

/** A reset as data/schedule.json has it. */
export interface BaseReset {
  name: string;
  when: string;
  day?: string;
  time: string;
}

export interface Reset {
  id: string;
  name: string;
  when: ResetWhen;
  day?: string; // weekly only
  time: string;
  own: boolean;
  edited: boolean; // a reset of the server whose time or day the user changed
}

export interface ResetEdit {
  time: string;
  day?: string;
}

export interface OwnReset {
  id: string;
  name: string;
  when: ResetWhen;
  day?: string;
  time: string;
}

export interface ResetStore {
  edits: Record<string, ResetEdit>;
  own: OwnReset[];
}

export const EMPTY_RESETS: ResetStore = { edits: {}, own: [] };
export const RESETS_FILE = "schedule_resets.json";

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;
const isDict = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === "object" && !Array.isArray(v);
export const resetBellKey = (id: string) => `reset:${id}`;
export const baseId = (index: number) => `r${index}`;

export function checkReset(draft: { name: string; when: string; day?: string; time: string }): string {
  if (!draft.name.trim()) return "Укажи название отката.";
  if (!TIME.test(draft.time)) return "Укажи время как ЧЧ:ММ, например 09:00.";
  if (draft.when !== "daily" && draft.when !== "weekly") return "Выбери: каждый день или раз в неделю.";
  if (draft.when === "weekly" && !DAYS.includes(draft.day ?? "")) return "Выбери день недели.";
  return "";
}

export function parseResets(text: string | null): ResetStore {
  try {
    const data = text ? JSON.parse(text) : null;
    if (!isDict(data)) return EMPTY_RESETS;
    const edits: Record<string, ResetEdit> = {};
    if (isDict(data.edits)) {
      for (const [id, raw] of Object.entries(data.edits)) {
        if (!isDict(raw) || typeof raw.time !== "string" || !TIME.test(raw.time)) continue;
        const day = typeof raw.day === "string" && DAYS.includes(raw.day) ? raw.day : undefined;
        edits[id] = day ? { time: raw.time, day } : { time: raw.time };
      }
    }
    const own: OwnReset[] = [];
    if (Array.isArray(data.own)) {
      for (const raw of data.own) {
        if (!isDict(raw) || typeof raw.id !== "string" || typeof raw.name !== "string") continue;
        const candidate = { name: raw.name, when: String(raw.when), day: typeof raw.day === "string" ? raw.day : undefined, time: String(raw.time) };
        if (checkReset(candidate)) continue;
        own.push({ id: raw.id, name: raw.name.trim(), when: candidate.when as ResetWhen, ...(candidate.when === "weekly" ? { day: candidate.day } : {}), time: candidate.time });
      }
    }
    return { edits, own };
  } catch {
    return EMPTY_RESETS;
  }
}

export const serializeResets = (store: ResetStore): string => JSON.stringify(store, null, 1) + "\n";

export function resolveResets(base: BaseReset[], store: ResetStore): Reset[] {
  const out: Reset[] = base.map((r, i) => {
    const id = baseId(i);
    const edit = store.edits[id];
    const when = r.when === "daily" ? "daily" : "weekly";
    const day = when === "weekly" ? (edit?.day ?? r.day) : undefined;
    return { id, name: r.name, when, ...(day ? { day } : {}), time: edit?.time ?? r.time, own: false, edited: edit !== undefined };
  });
  for (const r of store.own) out.push({ ...r, own: true, edited: false });
  return out;
}

/** The occurrences of a reset in the week: seven for a daily one, one for a weekly one; each is a one-minute event. */
export function resetEvents(reset: Pick<Reset, "name" | "when" | "day" | "time">): ScheduleEvent[] {
  const [h, m] = reset.time.split(":").map(Number);
  const end = h * 60 + m + 1;
  const stop = end >= 1440 ? "24:00" : `${String(Math.floor(end / 60)).padStart(2, "0")}:${String(end % 60).padStart(2, "0")}`;
  const days = reset.when === "daily" ? DAYS : [reset.day ?? "mon"];
  return days.map((day) => ({ day, start: reset.time, end: stop, name: reset.name, kind: "Откат" }));
}

export function nextOwnId(store: ResetStore): string {
  const used = store.own.map((r) => Number(r.id.replace(/\D/g, "")) || 0);
  return `own${Math.max(0, ...used) + 1}`;
}
