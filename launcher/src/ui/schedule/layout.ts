// Geometry and grouping of the schedule screen: pure functions (tested), no React.
import { DAY, DAYS, MINUTE, ScheduleEvent, startsAt, weekStart } from "../../core/schedule/reminders";
import { endOf } from "../../core/schedule/timing";

export const HOUR_PX = 28; // height of one shown hour
export const FOLD_TOP = 18; // 00:00–02:00 has no events: folded
export const FOLD_MID = 40; // 04:00–10:00 has no events: folded, the resets are drawn inside
const SHOWN_A = 2 * HOUR_PX; // 02:00–04:00
const SHOWN_B = 14 * HOUR_PX; // 10:00–24:00
export const GRID_H = FOLD_TOP + SHOWN_A + FOLD_MID + SHOWN_B;
export const FOLD_MID_Y = FOLD_TOP + SHOWN_A;
export const SNAP_MIN = 15;

/** Pixel row of a minute of the day on the folded day axis. */
export function yOf(minute: number): number {
  const h = minute / 60;
  if (h <= 2) return (FOLD_TOP * h) / 2;
  if (h <= 4) return FOLD_TOP + (h - 2) * HOUR_PX;
  if (h < 10) return FOLD_MID_Y + (FOLD_MID * (h - 4)) / 6;
  return FOLD_MID_Y + FOLD_MID + (h - 10) * HOUR_PX;
}

/** The minute of the day under a pixel row, snapped; null inside a folded band (nothing can start there). */
export function minuteAt(y: number): number | null {
  if (y < 0 || y > GRID_H) return null;
  if (y < FOLD_TOP) return null;
  if (y <= FOLD_MID_Y) return snap(120 + ((y - FOLD_TOP) / HOUR_PX) * 60);
  if (y < FOLD_MID_Y + FOLD_MID) return null;
  return snap(600 + ((y - FOLD_MID_Y - FOLD_MID) / HOUR_PX) * 60);
}

export const snap = (minute: number) => Math.min(1440, Math.max(0, Math.round(minute / SNAP_MIN) * SNAP_MIN));

export const hm = (minute: number) => `${String(Math.floor(minute / 60) % 24).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;

export const toMinutes = (text: string) => {
  const [h, m] = text.split(":").map(Number);
  return h * 60 + m;
};

/** A weekly event with its start and end as minutes of its day (an end before the start is cut at midnight). */
export interface Slot {
  event: ScheduleEvent;
  s: number;
  e: number;
}

export function slotOf(event: ScheduleEvent): Slot | null {
  const s = toMinutes(event.start);
  let e = toMinutes(event.end);
  if (e === s) return null; // the zero-length «Откат» records are resets, not events
  if (e < s || e === 0) e = 1440;
  return { event, s, e };
}

export interface Placed extends Slot {
  lane: number;
  lanes: number;
}

/** Events of one day side by side: overlapping ones share a row of lanes, each as wide as its cluster allows. */
export function placeDay(events: ScheduleEvent[]): Placed[] {
  const slots = events.map(slotOf).filter((x): x is Slot => x !== null).sort((a, b) => a.s - b.s || a.e - b.e);
  const out: Placed[] = [];
  let cluster: Placed[] = [];
  let laneEnds: number[] = [];
  let clusterEnd = -1;
  const close = () => {
    for (const p of cluster) p.lanes = laneEnds.length;
    out.push(...cluster);
    cluster = [];
    laneEnds = [];
  };
  for (const slot of slots) {
    if (cluster.length && slot.s >= clusterEnd) close();
    let lane = laneEnds.findIndex((end) => end <= slot.s);
    if (lane < 0) { lane = laneEnds.length; laneEnds.push(slot.e); } else laneEnds[lane] = slot.e;
    clusterEnd = Math.max(clusterEnd < 0 ? 0 : clusterEnd, slot.e);
    cluster.push({ ...slot, lane, lanes: 1 });
  }
  close();
  return out;
}

export type Tone = "blue" | "green" | "teal" | "amber" | "orange" | "purple" | "gray";

/** The colour of an event from its «color» field (Russian names, as in data/schedule.json). */
export function toneOf(event: ScheduleEvent): Tone {
  const c = String(event.color ?? "").toLowerCase();
  if (c.startsWith("гол") || c.startsWith("син")) return "blue";
  if (c.startsWith("зел") || c.startsWith("зёл")) return "green";
  if (c.startsWith("бир")) return "teal";
  if (c.startsWith("жел") || c.startsWith("жёл")) return "amber";
  if (c.startsWith("оранж")) return "orange";
  if (c.startsWith("фиол")) return "purple";
  return "gray";
}

export const TONE_NAME: Record<Tone, string> = {
  blue: "Голубой", green: "Зелёный", teal: "Бирюзовый", amber: "Жёлтый", orange: "Оранжевый", purple: "Фиолетовый", gray: "Серый",
};

/** One occurrence of a weekly event on the timeline: absolute naive-MSK milliseconds. */
export interface Occurrence {
  event: ScheduleEvent;
  start: number;
  end: number;
}

/** Occurrences that overlap [from, to): this week, the week before (an overnight run) and the weeks after. */
export function occurrencesIn(events: ScheduleEvent[], from: number, to: number): Occurrence[] {
  const out: Occurrence[] = [];
  for (let monday = weekStart(from) - 7 * DAY; monday < to; monday += 7 * DAY) {
    for (const event of events) {
      if (toMinutes(event.start) === toMinutes(event.end)) continue;
      const start = startsAt(event, monday);
      const end = endOf(event, start);
      if (end > from && start < to) out.push({ event, start, end });
    }
  }
  return out.sort((a, b) => a.start - b.start || a.end - b.end);
}

/** Lanes for a list of overlapping occurrences on the ribbon: the lane of each, in order. */
export function ribbonLanes(items: Occurrence[]): number[] {
  const ends: number[] = [];
  return items.map((o) => {
    let lane = ends.findIndex((end) => end <= o.start);
    if (lane < 0) { lane = ends.length; ends.push(o.end); } else ends[lane] = o.end;
    return lane;
  });
}

export const dayIndex = (day: string) => DAYS.indexOf(day);

/** Minutes between two naive times as «1 ч 47 мин», «3 дн», for the countdown. */
export function countdown(ms: number): string {
  const minutes = Math.max(0, Math.floor(ms / MINUTE));
  if (minutes >= 48 * 60) return `${Math.floor(minutes / 1440)} дн`;
  if (minutes >= 24 * 60) return `1 д ${Math.floor((minutes % 1440) / 60)} ч`;
  if (minutes >= 60) return minutes % 60 ? `${Math.floor(minutes / 60)} ч ${minutes % 60} мин` : `${Math.floor(minutes / 60)} ч`;
  return `${minutes} мин`;
}
