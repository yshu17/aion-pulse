import { describe, expect, it } from "vitest";

import { naiveMs } from "../../core/chat/tailer";
import { ScheduleEvent } from "../../core/schedule/reminders";
import { countdown, GRID_H, hm, minuteAt, occurrencesIn, placeDay, ribbonLanes, slotOf, toneOf, yOf } from "./layout";

const ev = (day: string, start: string, end: string, name = "x", color = "Голубой"): ScheduleEvent => ({ day, start, end, name, color });

describe("schedule layout", () => {
  it("folds the empty bands: 00–02 and 04–10 are short, the shown hours are full", () => {
    expect(yOf(0)).toBe(0);
    expect(yOf(120)).toBe(18);
    expect(yOf(240)).toBe(18 + 56); // two shown hours
    expect(yOf(600) - yOf(240)).toBe(40); // the whole 04–10 band is 40 px
    expect(yOf(1440)).toBe(GRID_H);
    expect(yOf(12 * 60) - yOf(10 * 60)).toBe(56);
  });

  it("finds the minute under a pixel row, snapped to 15 min, nothing inside a folded band", () => {
    expect(minuteAt(yOf(18 * 60))).toBe(18 * 60);
    expect(minuteAt(yOf(18 * 60 + 37))).toBe(18 * 60 + 30);
    expect(minuteAt(yOf(3 * 60))).toBe(180);
    expect(minuteAt(5)).toBeNull(); // 00–02
    expect(minuteAt(yOf(7 * 60))).toBeNull(); // 04–10
    expect(minuteAt(-1)).toBeNull();
    expect(minuteAt(GRID_H + 1)).toBeNull();
  });

  it("puts overlapping events in lanes of their cluster and leaves a lone event full width", () => {
    const placed = placeDay([ev("wed", "20:00", "00:00", "Аренка"), ev("wed", "20:00", "21:00", "Инга"), ev("wed", "21:00", "23:00", "Дерадикон"),
      ev("wed", "10:00", "12:00", "Один"), ev("wed", "09:00", "09:00", "Откат")]);
    const by = Object.fromEntries(placed.map((p) => [p.event.name, [p.lane, p.lanes, p.s, p.e]]));
    expect(by["Один"]).toEqual([0, 1, 600, 720]);
    expect(by["Инга"]).toEqual([0, 2, 1200, 1260]); // the shorter of two equal starts goes first
    expect(by["Аренка"]).toEqual([1, 2, 1200, 1440]); // «00:00» as an end is the end of the day
    expect(by["Дерадикон"]).toEqual([0, 2, 1260, 1380]); // takes the lane Инга left free
    expect(by["Откат"]).toBeUndefined(); // zero length: a reset, not an event
    expect(slotOf(ev("mon", "09:00", "09:00"))).toBeNull();
  });

  it("names the colour of an event", () => {
    expect(["Голубой", "Зелёный", "Бирюзовый", "Жёлтый", "Фиолетовый", "Оранжевый", "", "Красный"].map((c) => toneOf(ev("mon", "1:00", "2:00", "x", c))))
      .toEqual(["blue", "green", "teal", "amber", "purple", "orange", "gray", "gray"]);
  });

  it("lists the occurrences of the next hours across midnight, the week edge and an overnight run", () => {
    const events = [ev("wed", "20:00", "00:00", "Аренка"), ev("thu", "02:00", "04:00", "Дерадикон"), ev("sun", "23:30", "01:30", "Ночной"),
      ev("wed", "09:00", "09:00", "Откат")];
    const from = naiveMs(2026, 10, 21, 12, 0); // Wednesday
    const names = (a: number, b: number) => occurrencesIn(events, a, b).map((o) => [o.event.name, hm((o.start / 60000) % 1440)]);
    expect(names(from, from + 24 * 3600000)).toEqual([["Аренка", "20:00"], ["Дерадикон", "02:00"]]);
    // Monday 00:30: the overnight run of Sunday is still going
    const monday = naiveMs(2026, 10, 26, 0, 30);
    expect(names(monday, monday + 3600000)).toEqual([["Ночной", "23:30"]]);
  });

  it("gives each overlapping ribbon item its own lane and reuses a free one", () => {
    const base = naiveMs(2026, 10, 21, 12, 0);
    const at = (h: number, len: number) => ({ event: ev("wed", "1:00", "2:00"), start: base + h * 3600000, end: base + (h + len) * 3600000 });
    expect(ribbonLanes([at(8, 4), at(9, 1), at(10, 1), at(12, 1)])).toEqual([0, 1, 1, 0]);
  });

  it("writes the countdown", () => {
    expect([0, 59 * 60000, 60 * 60000, 107 * 60000, 29 * 3600000, 50 * 3600000].map(countdown))
      .toEqual(["0 мин", "59 мин", "1 ч", "1 ч 47 мин", "1 д 5 ч", "2 дн"]);
  });
});
