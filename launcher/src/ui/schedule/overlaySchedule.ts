import { ScheduleEvent } from "../../core/schedule/reminders";
import type { OverlayEvent, OverlayState } from "../overlayWindow";
import { countdown, hm, occurrencesIn, Occurrence, toneOf } from "./layout";

const DAY_MS = 86_400_000;
const clock = (ms: number) => hm(Math.floor((((ms % DAY_MS) + DAY_MS) % DAY_MS) / 60_000));

function item(o: Occurrence, left: string): OverlayEvent {
  return { name: o.event.name, tone: toneOf(o.event), from: clock(o.start), to: clock(o.end), left };
}

/** What runs now (ending soonest first, at most two) and what starts next, for the overlay over the game. */
export function overlaySchedule(events: ScheduleEvent[], now: number): OverlayState["schedule"] {
  const around = occurrencesIn(events, now - DAY_MS, now + 2 * DAY_MS);
  const current = around.filter((o) => o.start <= now && now < o.end).sort((a, b) => a.end - b.end).slice(0, 2)
    .map((o) => item(o, `ещё ${countdown(o.end - now + 59_999)}`));
  const upcoming = around.filter((o) => o.start > now).sort((a, b) => a.start - b.start)[0];
  return { current, next: upcoming ? item(upcoming, `через ${countdown(upcoming.start - now + 59_999)}`) : null };
}
