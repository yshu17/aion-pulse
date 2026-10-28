// Geometry and grouping of the schedule screen: pure functions (tested), no React.
import { DAY, DAYS, MINUTE, ScheduleEvent, startsAt, weekStart } from "../../core/schedule/reminders";
import { endOf } from "../../core/schedule/timing";

export const HOUR_PX = 28; // the least height of one shown hour
export const FOLD_PX = 8; // a run of hours without events: one thin strip
export const SNAP_MIN = 15;
const DEFAULT_HOURS: [number, number] = [600, 1440]; // nothing to show: 10:00–24:00, so a new event can still be drawn

/**
 * The day axis of the grid, from the events shown: an hour with an event is shown, at least HOUR_PX tall and taller
 * when an event in it needs room for its text; a run of hours without events is one thin strip; the resets of an hour
 * get their own band at its start, as tall as their chips.
 */
export interface Band {
  kind: "hours" | "fold" | "resets";
  from: number; // minutes of the day
  to: number;
  y: number; // pixel row of its top
  h: number;
}
export interface Axis { bands: Band[]; height: number }

/** An event to show (minutes of its day) and the height its card needs; a band of resets at a minute and its height. */
export interface AxisInput {
  spans: { s: number; e: number; px: number }[];
  resets: { minute: number; px: number }[];
}

export function buildAxis({ spans, resets }: AxisInput): Axis {
  const need = new Array<number>(24).fill(0); // px each hour must have, 0 for an hour without events
  const shown = new Array<boolean>(24).fill(false);
  const list = spans.length ? spans : [{ s: DEFAULT_HOURS[0], e: DEFAULT_HOURS[1], px: 0 }];
  for (const { s, e, px } of list) {
    const perHour = (px * 60) / Math.max(1, e - s);
    for (let h = Math.floor(s / 60); h < Math.ceil(e / 60) && h < 24; h += 1) {
      shown[h] = true;
      need[h] = Math.max(need[h], perHour);
    }
  }
  const resetPx = new Map<number, number>();
  for (const r of resets) {
    const at = Math.floor(r.minute / 60) * 60;
    resetPx.set(at, Math.max(resetPx.get(at) ?? 0, r.px));
  }
  const bands: Band[] = [];
  let y = 0;
  const add = (kind: Band["kind"], from: number, to: number, h: number) => {
    const last = bands[bands.length - 1];
    if (last && last.kind === kind && kind !== "resets" && last.to === from && (kind === "fold" || last.h / (last.to - last.from) === h / (to - from))) {
      last.to = to; // one run of hours of the same height, or one strip
      if (kind === "hours") last.h += h;
      y = last.y + last.h;
      return;
    }
    bands.push({ kind, from, to, y, h });
    y += h;
  };
  for (let hour = 0; hour < 24; hour += 1) {
    const from = hour * 60;
    const r = resetPx.get(from);
    if (r !== undefined) add("resets", from, from, r);
    if (shown[hour]) add("hours", from, from + 60, Math.max(HOUR_PX, Math.ceil(need[hour])));
    else add("fold", from, from + 60, FOLD_PX);
  }
  return { bands, height: y };
}

/** Pixel row of a minute of the day. `end`: the minute ends something, so a band of resets at it comes after. */
export function yOf(axis: Axis, minute: number, end = false): number {
  for (const b of axis.bands) {
    if (b.kind === "resets") {
      if (minute === b.from && end) return b.y;
      continue;
    }
    if (minute >= b.from && (minute < b.to || (minute === b.to && (end || b.to === 1440)))) {
      return b.y + (b.h * (minute - b.from)) / (b.to - b.from);
    }
  }
  return axis.height;
}

/** The minute of the day under a pixel row, snapped; null in a strip or the resets (nothing can start there). */
export function minuteAt(axis: Axis, y: number): number | null {
  if (y < 0 || y > axis.height) return null;
  const b = axis.bands.find((x) => y >= x.y && y <= x.y + x.h && x.kind === "hours");
  if (!b) return null;
  return Math.min(b.to, Math.max(b.from, snap(b.from + ((y - b.y) / b.h) * (b.to - b.from))));
}

const EM_PX = 0.57; // the average width of a letter of a card title, in em (semibold)
const FONT_MAX = 12;
const FONT_MIN = 10; // a word longer than the card is at this size breaks
const CARD_PAD = 10; // the card's padding and border and the 1 px gap above and below it
export const CARD_SIDE = 16; // the gap between lanes and the card's padding and border, left and right
const TIME_W = 66; // «20:00–21:00» on one line; a narrower card puts the end on a second line
const MAX_LINES = 4; // a longer name is cut with «…»

/** The width of a text in a card title at a size: the screen's measure, or an estimate (tests, no canvas). */
export type Measure = (text: string, size: number) => number;
const estimate: Measure = (text, size) => text.length * size * EM_PX;

/** The size of a card title: 12 px, smaller (down to 10) until its longest word fits the card's width. */
export function cardFont(name: string, width: number, measure: Measure = estimate): number {
  const words = name.split(/\s+/).filter(Boolean);
  for (let size = FONT_MAX; size > FONT_MIN; size -= 1) if (words.every((w) => measure(w, size) <= width - CARD_SIDE)) return size;
  return FONT_MIN;
}

/**
 * The name as a card shows it: a word wider than the card even at the smallest size is cut to fit, with «…» (a word
 * broken in the middle reads worse). `measure` gives the width of a text at the card's font.
 */
export function fitName(name: string, width: number, measure: (text: string) => number): string {
  const room = width - CARD_SIDE;
  return name.split(" ").map((word) => {
    if (measure(word) <= room) return word;
    let cut = word;
    while (cut.length > 1 && measure(cut + "…") > room) cut = cut.slice(0, -1);
    return cut + "…";
  }).join(" ");
}

/** How tall a card must be to show its whole name (up to four lines, words kept whole) and its time, at a width. */
export function cardNeed(name: string, width: number, measure: Measure = estimate): number {
  const font = cardFont(name, width, measure);
  const perLine = Math.max(3, Math.floor((width - CARD_SIDE) / (font * EM_PX)));
  let lines = 1;
  let used = 0;
  for (const word of name.split(/\s+/).filter(Boolean)) {
    const len = word.length;
    if (used === 0) { lines += Math.floor((len - 1) / perLine); used = ((len - 1) % perLine) + 1; continue; }
    if (used + 1 + len <= perLine) { used += 1 + len; continue; }
    lines += 1 + Math.floor((len - 1) / perLine);
    used = ((len - 1) % perLine) + 1;
  }
  const timeLines = width - CARD_SIDE < TIME_W ? 2 : 1;
  return CARD_PAD + Math.min(MAX_LINES, lines) * (font + 2) + timeLines * 13;
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
const HOUR_MS = 3_600_000;
export const RIBBON_HALF = 12 * HOUR_MS; // the ribbon shows 12 hours before now and 12 after
export const RIBBON_FOCUS = 4 * HOUR_MS; // the hours on each side of now that are magnified
const FOCUS_X = 0.3; // the magnified hours take 30 % of the width on each side of now (60 % in all)

/**
 * Where a moment `ms` from now is on the ribbon, 0…1: a magnifier, the 4 hours on each side of now take the middle 60 %,
 * the other 8 hours on each side are squeezed into the outer 20 %. Outside the ribbon: its edge.
 */
export function ribbonX(ms: number): number {
  const d = Math.min(RIBBON_HALF, Math.abs(ms));
  const x = d <= RIBBON_FOCUS ? (d / RIBBON_FOCUS) * FOCUS_X : FOCUS_X + ((d - RIBBON_FOCUS) / (RIBBON_HALF - RIBBON_FOCUS)) * (0.5 - FOCUS_X);
  return 0.5 + Math.sign(ms) * x;
}

/**
 * Lanes for boxes on a line (`from`…`to`, any unit; `to` already includes the room the box needs for its text): each box
 * takes the first lane where it does not touch the one before it, so neighbours with no room for their names go one
 * above the other instead of side by side.
 */
export function packLanes(boxes: { from: number; to: number }[], gap = 0): number[] {
  const order = boxes.map((_, i) => i).sort((a, b) => boxes[a].from - boxes[b].from);
  const ends: number[] = [];
  const lanes = new Array<number>(boxes.length).fill(0);
  for (const i of order) {
    let lane = ends.findIndex((end) => end + gap <= boxes[i].from);
    if (lane < 0) { lane = ends.length; ends.push(0); }
    ends[lane] = boxes[i].to;
    lanes[i] = lane;
  }
  return lanes;
}

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
