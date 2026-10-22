/**
 * Schedule time helpers: MSK server clock, local display, event ends, «через 40 мин», reminder keys — the port of
 * core/schedule/timing.py.
 *
 * Event times in data/schedule.json are server time (MSK, UTC+3, no daylight saving); naive datetimes here are MSK
 * wall-clock milliseconds. A time zone is a function from a UTC instant (ms) to its offset in minutes, so summer and
 * winter time work; `fixedZone` makes Python's timezone(timedelta(...)), `localZone` is the computer's zone.
 * `parseEvents(text)` reads the weekly events from the file text (null = missing file).
 */

import { DAY, DAYS, dayStart, hhmm, hourMinute, MINUTE, ScheduleEvent, weekday } from "./reminders";

export type Zone = (utcMs: number) => number;

export const MSK_OFFSET = 180;
export const fixedZone = (minutes: number): Zone => () => minutes;
export const localZone: Zone = (utcMs) => -new Date(utcMs).getTimezoneOffset();

export const DAY_NAMES: Record<string, string> = {
  mon: "Понедельник", tue: "Вторник", wed: "Среда", thu: "Четверг", fri: "Пятница", sat: "Суббота", sun: "Воскресенье",
};
export const LEADS: [string, number][] = [["5 мин", 5], ["15 мин", 15], ["30 мин", 30], ["1 час", 60]]; // SN-8
export const DEFAULT_LEAD = 5;
export const DAYS_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]; // the chips of the form, Monday first

/**
 * The weekly events of data/schedule.json; a missing or broken file gives an empty schedule. Like Python's
 * list(data.get("events", [])), a string gives its characters and an object its keys.
 */
export function parseEvents(text: string | null): ScheduleEvent[] {
  if (text === null) return [];
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return [];
  }
  if (data === null || typeof data !== "object" || Array.isArray(data)) return [];
  const events = (data as Record<string, unknown>).events ?? [];
  if (Array.isArray(events)) return [...events];
  if (typeof events === "string") return [...events] as unknown as ScheduleEvent[];
  if (events !== null && typeof events === "object") return Object.keys(events) as unknown as ScheduleEvent[];
  throw new TypeError("events is not iterable");
}

/** Naive MSK wall-clock time, the clock the schedule is written in. */
export function mskNow(utcMs: number = Date.now()): number {
  return utcMs + MSK_OFFSET * MINUTE;
}

/** An MSK wall-clock time in the computer's (or the given) time zone, as naive local milliseconds. */
export function toLocal(msk: number, tz: Zone = localZone): number {
  const utc = msk - MSK_OFFSET * MINUTE;
  return utc + tz(utc) * MINUTE;
}

/** The end of one occurrence; «24:00» and an end before the start roll over to the next day. */
export function endOf(event: Pick<ScheduleEvent, "end">, start: number): number {
  const [hour, minute] = hourMinute(event.end);
  const end = dayStart(start) + (hour * 60 + minute) * MINUTE;
  return end > start ? end : end + DAY;
}

/** «идёт · ещё 25 мин», «через 40 мин», «через 3 ч 5 мин», «завтра» — all in MSK. */
export function untilText(start: number, end: number, now: number): string {
  if (start <= now && now < end) return `идёт · ещё ${span(Math.floor((end - now) / MINUTE))}`;
  const minutes = Math.floor((start - now) / MINUTE);
  if (minutes >= 24 * 60) return "через " + (minutes >= 48 * 60 ? `${Math.floor(minutes / (24 * 60))} дн` : "сутки");
  return `через ${span(minutes)}`;
}

function span(minutes: number): string {
  minutes = Math.max(minutes, 0);
  if (minutes < 60) return `${minutes} мин`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`;
}

/** «МСК» or «UTC+2» for the local zone at that moment (summer and winter time differ). */
export function zoneName(msk: number, tz: Zone = localZone): string {
  const offset = tz(msk - MSK_OFFSET * MINUTE);
  if (offset === MSK_OFFSET) return "МСК";
  const sign = offset >= 0 ? "+" : "−";
  const total = Math.abs(offset);
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return `UTC${sign}${hours}` + (rest ? `:${String(rest).padStart(2, "0")}` : "");
}

/** The saved id of a weekly event the user wants to be reminded of. */
export function bellKey(event: ScheduleEvent): string {
  return `${event.day}|${event.start}|${event.name}`;
}

export function leadLabel(minutes: number): string {
  return LEADS.find(([, value]) => value === minutes)?.[0] ?? "5 мин";
}

/** «20:00–21:00» in local time. */
export function timeRange(start: number, end: number, tz: Zone = localZone): string {
  return `${hhmm(toLocal(start, tz))}–${hhmm(toLocal(end, tz))}`;
}

export function todayKey(now: number): string {
  return DAYS[weekday(now)];
}
