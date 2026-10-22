/**
 * Schedule reminders: which events start soon and were not announced yet — the port of core/schedule/reminders.py.
 *
 * Times in `events` are server time (MSK, the same clock the watcher uses). A naive datetime is milliseconds of that
 * wall clock (see chat/tailer.naiveMs): read it with the UTC getters, never with the local ones.
 */

import { pyInt, pyMod } from "../py";

export const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]; // datetime.weekday() order

export const MINUTE = 60_000;
export const DAY = 24 * 60 * MINUTE;

export interface ScheduleEvent {
  day: string;
  start: string;
  end: string;
  name: string;
  kind?: string;
  group?: string;
  color?: string;
  maps?: string[];
  [key: string]: unknown;
}

/** Python datetime.weekday(): Monday 0 … Sunday 6. */
export function weekday(at: number): number {
  return (new Date(at).getUTCDay() + 6) % 7;
}

/** Midnight of the day of `at`. */
export function dayStart(at: number): number {
  return at - pyMod(at, DAY);
}

const pad = (n: number, width = 2) => String(n).padStart(width, "0");

/** Python datetime.isoformat() of a naive time: «2026-10-22T20:00:00» (milliseconds as «.ffffff» when present). */
export function isoformat(at: number): string {
  const d = new Date(at);
  const base = `${pad(d.getUTCFullYear(), 4)}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${hhmm(at)}:${pad(d.getUTCSeconds())}`;
  return d.getUTCMilliseconds() ? `${base}.${pad(d.getUTCMilliseconds() * 1000, 6)}` : base;
}

/** strftime «%H:%M». */
export function hhmm(at: number): string {
  const d = new Date(at);
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

/** strftime «%H:%M:%S». */
export function hhmmss(at: number): string {
  return `${hhmm(at)}:${pad(new Date(at).getUTCSeconds())}`;
}

/** strftime «%d.%m». */
export function ddmm(at: number): string {
  const d = new Date(at);
  return `${pad(d.getUTCDate())}.${pad(d.getUTCMonth() + 1)}`;
}

/** «20:30» -> [20, 30] with Python int() on each part. */
export function hourMinute(text: string): [number, number] {
  const parts = text.split(":");
  if (parts.length !== 2) throw new TypeError(`not a time: ${text}`);
  return [pyInt(parts[0]), pyInt(parts[1])];
}

function dayIndex(day: string): number {
  const index = DAYS.indexOf(day);
  if (index < 0) throw new TypeError(`unknown day: ${day}`);
  return index;
}

/** Start of the event in the week that begins at weekStart (a Monday, 00:00). */
export function startsAt(event: ScheduleEvent, weekStartAt: number): number {
  const [hour, minute] = hourMinute(event.start);
  return weekStartAt + dayIndex(event.day) * DAY + (hour * 60 + minute) * MINUTE;
}

/** Monday 00:00 of the week that contains now. */
export function weekStart(now: number): number {
  return dayStart(now - weekday(now) * DAY);
}

/** Stable id of one occurrence: the same event in the same week is announced once. */
export function reminderKey(event: ScheduleEvent, at: number): string {
  return `${event.day}|${event.start}|${event.name}|${isoformat(at)}`;
}

/**
 * Events that start within leadMin minutes from now (not in the past), not yet in sent.
 * Returns [key, event, start] tuples, earliest first. The caller stores the keys it has shown into sent.
 */
export function dueReminders(events: ScheduleEvent[], now: number, leadMin: number,
                             sent: Set<string>): [string, ScheduleEvent, number][] {
  if (leadMin < 0) throw new RangeError("lead_min must be >= 0");
  const base = weekStart(now);
  const windowEnd = now + leadMin * MINUTE;
  const found: [string, ScheduleEvent, number][] = [];
  for (const event of events) {
    // an event can start later this week or, for a week-boundary case, last week (it is still running now)
    for (const shift of [-7, 0, 7]) {
      const at = startsAt(event, base + shift * DAY);
      if (now <= at && at <= windowEnd) {
        const key = reminderKey(event, at);
        if (!sent.has(key)) found.push([key, event, at]);
      }
    }
  }
  return found.sort((a, b) => a[2] - b[2]);
}

/** Weekly occurrences that started in (after, until], earliest first (SN-8: missed while the program was closed). */
export function occurrencesBetween(events: ScheduleEvent[], after: number, until: number): [ScheduleEvent, number][] {
  const found: [ScheduleEvent, number][] = [];
  for (let monday = weekStart(after); monday <= until; monday += 7 * DAY) {
    for (const event of events) {
      const at = startsAt(event, monday);
      if (after < at && at <= until) found.push([event, at]);
    }
  }
  return found.sort((a, b) => a[1] - b[1]);
}
