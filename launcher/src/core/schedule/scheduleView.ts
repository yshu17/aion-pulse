/**
 * Pure schedule views — the port of core/schedule/schedule_view.py. Event times and naive `now` use the watcher's MSK
 * clock (milliseconds, see reminders.ts).
 *
 * Kept 1:1 with Python, known quirk included: dayBlocks treats a zero-length event («Откат» 09:00–09:00) as running
 * to midnight.
 */

import { DAY, DAYS, dayStart, ddmm, hhmmss, hourMinute, MINUTE, ScheduleEvent, startsAt, weekday, weekStart } from "./reminders";
import { MSK_OFFSET, Zone } from "./timing";

/** Events starting on `day`, ordered by their start time. */
export function eventsForDay(events: ScheduleEvent[], day: string): ScheduleEvent[] {
  return events.filter((event) => event.day === day).sort((a, b) => cmp(a.start, b.start));
}

/** Events whose listed start day is today in MSK. */
export function todayEvents(events: ScheduleEvent[], now: number): ScheduleEvent[] {
  return eventsForDay(events, DAYS[weekday(now)]);
}

function cmp(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/**
 * Next weekly occurrences, including events running at `now`: [event, actual start]. The end is exclusive; an event
 * ending exactly at `now` is no longer running.
 */
export function nextEvents(events: ScheduleEvent[], now: number, limit: number): [ScheduleEvent, number][] {
  if (limit <= 0 || !events.length) return [];
  const base = weekStart(now);
  const found: [ScheduleEvent, number][] = [];
  let weekOffset = -1; // previous Sunday's overnight event can still be running on Monday
  while (found.length < limit) {
    const monday = base + weekOffset * 7 * DAY;
    for (const event of events) {
      const start = startsAt(event, monday);
      if (start >= now || (start <= now && now < endExclusive(event, start))) found.push([event, start]);
    }
    weekOffset += 1;
  }
  return found.sort((a, b) => a[1] - b[1]).slice(0, limit);
}

/** schedule_view._end_at: unlike timing.endOf, an end equal to the start stays (a zero-length event). */
function endExclusive(event: ScheduleEvent, start: number): number {
  const [hour, minute] = hourMinute(event.end);
  const end = dayStart(start) + (hour * 60 + minute) * MINUTE;
  return end < start ? end + DAY : end;
}

/** SN-7: the event's kind for the filter («Арены» groups the arena brackets); without one, its own name. */
export function kindOf(event: ScheduleEvent): string {
  return event.kind || event.name;
}

/** Each kind once, in the order of the data. */
export function kinds(events: ScheduleEvent[]): string[] {
  return [...new Set(events.map(kindOf))];
}

/** The events whose kind is not hidden by the filter. */
export function visible(events: ScheduleEvent[], hidden: Set<string>): ScheduleEvent[] {
  return events.filter((event) => !hidden.has(kindOf(event)));
}

/**
 * SN-7 «На карте»: the zone map id of an event (field «maps»); of two zones, the one of the player's side —
 * «dark» (Asmodians) prefers 220…, «light» (Elyos) 210…; null when the event has no place.
 */
export function mapFor(event: ScheduleEvent, side: string): string | null {
  const maps = event.maps || [];
  if (!maps.length) return null;
  const prefix = side === "dark" ? "220" : "210";
  return maps.find((m) => m.startsWith(prefix)) ?? maps[0];
}

function minutes(text: string): number {
  const [hour, minute] = hourMinute(text);
  return hour * 60 + minute;
}

/**
 * Day strip: [event, start, end, lane] in minutes from midnight, sorted by start; an event that runs past midnight is
 * cut at 1440; overlapping events go to the next free lane.
 */
export function dayBlocks(events: ScheduleEvent[]): [ScheduleEvent, number, number, number][] {
  const blocks: [ScheduleEvent, number, number, number][] = [];
  const laneEnds: number[] = [];
  const sorted = events.map((event) => [event, minutes(event.start)] as const).sort((a, b) => a[1] - b[1]);
  for (const [event, start] of sorted) {
    let end = minutes(event.end);
    if (end <= start) end = 1440;
    let lane = laneEnds.findIndex((busyUntil) => busyUntil <= start);
    if (lane < 0) {
      lane = laneEnds.length;
      laneEnds.push(end);
    } else {
      laneEnds[lane] = end;
    }
    blocks.push([event, start, end, lane]);
  }
  return blocks;
}

export const GROUPS = ["Дерадиконы", "PVP арена", "Арены Хаоса и Доблести", "Осады", "Прочее"]; // menu order

/** The groups present in `events`, in the menu order; the user's own groups after the known ones, sorted. */
export function groups(events: ScheduleEvent[]): string[] {
  const present = new Set(events.map(groupOf));
  const known = GROUPS.filter((g) => present.has(g));
  return [...known, ...[...present].filter((g) => !GROUPS.includes(g)).sort(cmp)];
}

/** Events whose group is not hidden by the group filter. */
export function groupHidden(events: ScheduleEvent[], hiddenGroups: Set<string>): ScheduleEvent[] {
  return events.filter((event) => !hiddenGroups.has(groupOf(event)));
}

/** Section of the schedule for an event: its own «group» if the user set one, else by kind (or name). */
export function groupOf(event: ScheduleEvent): string {
  if (event.group) return event.group;
  const kind = kindOf(event);
  const name = event.name;
  if (kind === "Арены" || kind === "Арена") return "Арены Хаоса и Доблести";
  if (kind.startsWith("PVP") || kind === "Potato") return "PVP арена";
  if (name.includes("Осада") || kind.includes("Осада")) return "Осады";
  if (name === "Дер" || name.includes("Дерадикон")) return "Дерадиконы";
  return "Прочее";
}

export const DAY_SHORT: Record<string, string> = { mon: "ПН", tue: "ВТ", wed: "СР", thu: "ЧТ", fri: "ПТ", sat: "СБ", sun: "ВС" };

/** «Сегодня» for the current weekday, else «ВТ 13.10» — the date of that weekday in this week. */
export function dayLabel(day: string, now: number, today: number): string {
  if (day === DAYS[weekday(today)] && day === DAYS[weekday(now)]) return "Сегодня";
  const target = weekStart(now) + DAYS.indexOf(day) * DAY;
  return `${DAY_SHORT[day]} ${ddmm(target)}`;
}

/** Server time (MSK, UTC+3) and this computer's time, both as HH:MM:SS. `utcNow` is a UTC instant in ms. */
export function clockPair(utcNow: number, localTz: Zone): [string, string] {
  return [hhmmss(utcNow + MSK_OFFSET * MINUTE), hhmmss(utcNow + localTz(utcNow) * MINUTE)];
}
