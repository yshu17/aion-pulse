/**
 * Reminders of belled schedule events: what to announce now, and what was missed while the program was closed — the
 * port of core/schedule/reminder_flow.py.
 *
 *     const planner = new ReminderPlanner();
 *     for (const r of planner.due(belledEvents, now, leadMin, tz)) notify(r.title, r.text); // every ~30 s, once each
 *     const missed = missedEvents(belledEvents, lastCheck, now);                              // at most MISSED_DAYS back
 *     const [title, text] = missedText(missed, tz);
 *
 * Times are naive MSK wall-clock milliseconds; `tz` is the zone the text shows them in. No timer, no file.
 */

import { DAY, dueReminders, hhmm, isoformat, occurrencesBetween, ScheduleEvent, weekday } from "./reminders";
import { nextEvents } from "./scheduleView";
import { bellKey, endOf, leadLabel, localZone, timeRange, toLocal, Zone } from "./timing";

export const MISSED_DAYS = 7; // events missed while the program was closed are reported for at most a week back
export const START_WINDOW_S = 120; // «Началось» is said within this many seconds after the start
export const WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];

export interface Reminder {
  key: string;
  title: string;
  text: string;
  event: ScheduleEvent;
  start: number;
  end: number;
}

export class ReminderPlanner {
  reminded = new Set<string>(); // occurrences already announced this run

  /** A reminder `leadMin` minutes before each belled event and one when it starts; each occurrence once. */
  due(belled: ScheduleEvent[], now: number, leadMin: number, tz: Zone = localZone): Reminder[] {
    const out: Reminder[] = [];
    for (const [key, event, start] of dueReminders(belled, now, leadMin, this.reminded)) {
      if (start - now < 60_000) continue; // the start reminder below covers it
      this.reminded.add(key);
      out.push(make(key, `Через ${leadLabel(leadMin)}: ${event.name}`, event, start, tz));
    }
    for (const [event, start] of nextEvents(belled, now, belled.length + 1)) {
      const key = `${bellKey(event)}|start|${isoformat(start)}`;
      const since = now - start;
      if (since >= 0 && since < START_WINDOW_S * 1000 && !this.reminded.has(key)) {
        this.reminded.add(key);
        out.push(make(key, `Началось: ${event.name}`, event, start, tz));
      }
    }
    return out;
  }
}

function make(key: string, title: string, event: ScheduleEvent, start: number, tz: Zone): Reminder {
  const end = endOf(event, start);
  return { key, title, text: `${timeRange(start, end, tz)} · расписание сервера`, event, start, end };
}

/** Belled events that started between the last check and now (no further back than `maxDays`). */
export function missedEvents(belled: ScheduleEvent[], last: number | null, now: number,
                             maxDays = MISSED_DAYS): [ScheduleEvent, number][] {
  if (last === null) return [];
  const from = Math.max(last, now - maxDays * DAY);
  return occurrencesBetween(belled, from, now).filter(([, at]) => now - at >= START_WINDOW_S * 1000);
}

/** [title, text] of the «missed while closed» notification: up to `shown` events with weekday and local time. */
export function missedText(missed: [ScheduleEvent, number][], tz: Zone = localZone, shown = 5): [string, string] {
  const names = missed.slice(0, shown).map(([e, at]) => `${e.name} (${WEEKDAYS[weekday(at)]} ${hhmm(toLocal(at, tz))})`);
  const more = missed.length > shown ? ` и ещё ${missed.length - shown}` : "";
  return [`Пропущено, пока программа была закрыта: ${missed.length}`, names.join(", ") + more];
}
