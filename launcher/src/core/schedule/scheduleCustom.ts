/**
 * SN-7: the user's own schedule changes, kept apart from data/schedule.json (the server's grid stays untouched) — the
 * port of core/schedule/schedule_custom.py. File `schedule_custom.json` next to config.json:
 *
 *     {"added": [{"day": "fri", "start": "19:30", "end": "20:30", "name": "Рейд"}], "removed": ["mon|02:00|Дер"]}
 *
 * - `Custom.load(text, write)` — `text` is the file (null = missing); a broken file means no changes; `write(text)`
 *   saves the file (null = never saved);
 * - `merge(base)` — the data events minus the removed ones, plus the added ones (kind «Свои»);
 * - `add`, `remove`, `edit(old, new)` — save at once; removing an own event drops it, removing a data event hides it
 *   by its key `day|start|name` (`eventKey`);
 * - `check(event)` — "" when the event is valid, else what to fix (in Russian, for the form).
 *
 * Known difference: Python's \d also takes non-ASCII digits (e.g. «٢»); here times are ASCII digits only.
 */

import { pyStr } from "../py";
import { DAYS, ScheduleEvent } from "./reminders";

export const OWN_KIND = "Свои";
const TIME = /^([01]\d|2[0-3]):[0-5]\d\n?$/; // Python's $ also matches before a final newline

export interface CustomData {
  added: ScheduleEvent[];
  removed: string[];
}

export type Writer = (text: string) => void;

export function eventKey(event: Pick<ScheduleEvent, "day" | "start" | "name">): string {
  return `${event.day}|${event.start}|${event.name}`;
}

const isDict = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

export function check(event: Record<string, unknown>): string {
  if (!DAYS.includes(event.day as string)) return "Выбери день недели.";
  const start = event.start ?? "";
  const end = event.end ?? "";
  if (typeof start !== "string" || typeof end !== "string") throw new TypeError("expected string or bytes-like object");
  if (!TIME.test(start) || !(TIME.test(end) || end === "24:00")) return "Укажи время как ЧЧ:ММ, например 19:30.";
  if (!pyStr(event.name ?? "").trim()) return "Укажи название события.";
  return "";
}

export class Custom {
  constructor(private write: Writer | null, public data: CustomData = { added: [], removed: [] }) {}

  static load(text: string | null, write: Writer | null): Custom {
    try {
      if (text === null) throw new Error("missing");
      const data = JSON.parse(text);
      if (!isDict(data)) throw new Error("not an object");
      const added = data.added ?? [];
      const removed = data.removed ?? [];
      if (!(Array.isArray(added) && Array.isArray(removed) && added.every((e) => isDict(e) && !check(e))
            && removed.every((k) => typeof k === "string"))) {
        throw new Error("unexpected schedule_custom.json");
      }
      const unique = new Map<string, ScheduleEvent>(); // old duplicates collapse, the last one wins
      for (const e of added as ScheduleEvent[]) unique.set(eventKey(e), e);
      return new Custom(write, { added: [...unique.values()], removed });
    } catch (error) {
      if (error instanceof TypeError) throw error;
      return new Custom(write);
    }
  }

  save(): void {
    this.write?.(JSON.stringify(this.data, null, 1) + "\n");
  }

  merge(base: ScheduleEvent[]): ScheduleEvent[] {
    const removed = new Set(this.data.removed);
    const addedKeys = new Set(this.data.added.map(eventKey)); // an own copy replaces the server event
    const kept = base.filter((event) => !removed.has(eventKey(event)) && !addedKeys.has(eventKey(event)));
    return [...kept, ...this.data.added.map((event) => ({ ...event, kind: OWN_KIND }))];
  }

  add(event: ScheduleEvent): void {
    for (const key of ["day", "start", "end", "name"]) if (!(key in event)) throw new TypeError(`KeyError: ${key}`);
    const clean: ScheduleEvent = { day: event.day, start: event.start, end: event.end, name: event.name };
    for (const key of ["group", "color"] as const) if (event[key]) clean[key] = event[key]; // optional, set in the form
    clean.name = clean.name.trim();
    const key = eventKey(clean); // the same day, start and name: replace, never duplicate
    this.data.added = [...this.data.added.filter((e) => eventKey(e) !== key), clean];
    this.save();
  }

  /** One event on several weekdays («на все дни»): saved as one entry per day. */
  addDays(event: ScheduleEvent, days: string[]): void {
    for (const day of days) this.add({ ...event, day });
  }

  remove(event: ScheduleEvent): void {
    const key = eventKey(event);
    if (this.data.added.some((e) => eventKey(e) === key)) {
      this.data.added = this.data.added.filter((e) => eventKey(e) !== key);
    } else if (!this.data.removed.includes(key)) {
      this.data.removed.push(key);
    }
    this.save();
  }

  edit(old: ScheduleEvent, next: ScheduleEvent): void {
    this.remove(old);
    this.add(next);
  }
}

export const DAY_BY_RU: Record<string, string> = { пн: "mon", вт: "tue", ср: "wed", чт: "thu", пт: "fri", сб: "sat", вс: "sun" };
export const DAY_RU: Record<string, string> = Object.fromEntries(Object.entries(DAY_BY_RU).map(([k, v]) => [v, k]));
const LINE = /^\s*(пн|вт|ср|чт|пт|сб|вс)\s+(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s+(.+?)\s*$/iu;

/** Python str.splitlines(): every line break Python knows, no empty part after a final break. */
export function pySplitlines(text: string): string[] {
  const lines = text.split(/\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/);
  if (lines[lines.length - 1] === "") lines.pop();
  return lines;
}

/** Every event as a text line: «пн 20:00-21:00 Название», Monday first, times as in the data. */
export function toText(events: ScheduleEvent[]): string {
  const order = (day: string) => (DAYS.includes(day) ? DAYS.indexOf(day) : 9);
  return [...events]
    .sort((a, b) => order(a.day) - order(b.day) || (a.start < b.start ? -1 : a.start > b.start ? 1 : 0))
    .map((e) => `${DAY_RU[e.day]} ${e.start}-${e.end} ${e.name}`)
    .join("\n");
}

/** Text lines back to events; returns [events, problems] — a bad line is reported, not dropped silently. */
export function parseText(text: string): [ScheduleEvent[], string[]] {
  const events: ScheduleEvent[] = [];
  const problems: string[] = [];
  pySplitlines(text).forEach((line, index) => {
    const number = index + 1;
    if (!line.trim()) return;
    const match = LINE.exec(line);
    if (!match) {
      problems.push(`строка ${number}: нужен вид «пн 20:00-21:00 Название»`);
      return;
    }
    const event = { day: DAY_BY_RU[match[1].toLowerCase()], start: match[2], end: match[3], name: match[4] };
    const problem = check(event);
    if (problem) problems.push(`строка ${number}: ${problem}`);
    else events.push(event);
  });
  return [events, problems];
}
