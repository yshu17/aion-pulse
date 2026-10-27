import { describe, expect, it } from "vitest";

import { naiveMs } from "../../core/chat/tailer";
import { ScheduleEvent } from "../../core/schedule/reminders";
import { buildAxis, cardFont, cardNeed, fitName, countdown, FOLD_PX, hm, HOUR_PX, minuteAt, occurrencesIn, placeDay, ribbonLanes, ribbonX, slotOf, toneOf, yOf } from "./layout";

const ev = (day: string, start: string, end: string, name = "x", color = "Голубой"): ScheduleEvent => ({ day, start, end, name, color });

describe("schedule layout", () => {
  it("shows only the hours with events; an empty run of hours is one thin strip", () => {
    const axis = buildAxis({ spans: [{ s: 600, e: 720, px: 0 }, { s: 1200, e: 1440, px: 0 }], resets: [] });
    expect(axis.bands.map((b) => [b.kind, b.from, b.to])).toEqual([
      ["fold", 0, 600], ["hours", 600, 720], ["fold", 720, 1200], ["hours", 1200, 1440],
    ]);
    expect(axis.bands.map((b) => b.h)).toEqual([FOLD_PX, 2 * HOUR_PX, FOLD_PX, 4 * HOUR_PX]);
    expect(axis.height).toBe(2 * FOLD_PX + 6 * HOUR_PX);
    expect(yOf(axis, 600)).toBe(FOLD_PX);
    expect(yOf(axis, 660)).toBe(FOLD_PX + HOUR_PX);
    expect(yOf(axis, 1440)).toBe(axis.height);
  });

  it("an hour grows until the event in it fits; a long event spreads its need over its hours", () => {
    const axis = buildAxis({ spans: [{ s: 600, e: 660, px: 70 }, { s: 720, e: 840, px: 70 }], resets: [] });
    expect(yOf(axis, 660) - yOf(axis, 600)).toBe(70); // one hour must hold all 70 px
    expect(yOf(axis, 780) - yOf(axis, 720)).toBe(HOUR_PX + 7); // two hours share 70 px: 35 each
  });

  it("puts the resets in their own band at their hour, as tall as their chips; an event ends above it and starts below", () => {
    const axis = buildAxis({ spans: [{ s: 480, e: 540, px: 0 }, { s: 540, e: 600, px: 0 }], resets: [{ minute: 540, px: 30 }] });
    expect(axis.bands.map((b) => [b.kind, b.from, b.to])).toEqual([["fold", 0, 480], ["hours", 480, 540], ["resets", 540, 540], ["hours", 540, 600], ["fold", 600, 1440]]);
    const band = axis.bands[2];
    expect(band.h).toBe(30);
    expect(yOf(axis, 540, true)).toBe(band.y); // the end of 08:00–09:00
    expect(yOf(axis, 540)).toBe(band.y + 30); // the start of 09:00–10:00
  });

  it("finds the minute under a pixel row, snapped to 15 min; nothing in a strip or the resets", () => {
    const axis = buildAxis({ spans: [{ s: 1080, e: 1200, px: 0 }], resets: [{ minute: 540, px: 24 }] });
    expect(minuteAt(axis, yOf(axis, 18 * 60))).toBe(18 * 60);
    expect(minuteAt(axis, yOf(axis, 18 * 60 + 37))).toBe(18 * 60 + 30);
    expect(minuteAt(axis, 2)).toBeNull();
    expect(minuteAt(axis, axis.bands.find((b) => b.kind === "resets")!.y + 5)).toBeNull();
    expect(minuteAt(axis, -1)).toBeNull();
    expect(minuteAt(axis, axis.height + 1)).toBeNull();
  });

  it("with nothing to show keeps 10:00–24:00, so a new event can still be drawn", () => {
    const axis = buildAxis({ spans: [], resets: [] });
    expect(axis.bands.filter((b) => b.kind === "hours").map((b) => [b.from, b.to])).toEqual([[600, 1440]]);
  });

  it("a card needs room for its whole name (up to three lines) and its time at its width", () => {
    expect(cardNeed("Аренка", 120)).toBe(cardNeed("Аренка", 300)); // one line either way
    expect(cardNeed("Ру / Астерия вместе", 50)).toBeGreaterThan(cardNeed("Ру / Астерия вместе", 200));
    expect(cardNeed("очень длинное название события которое не влезет", 40)).toBe(cardNeed("и ещё длиннее название события которое не влезет никак", 40)); // four lines at most
    expect(cardNeed("Око", 54)).toBe(cardNeed("Око", 200) + 13); // a narrow card puts the end of its time on a second line
  });

  it("a card title gets smaller until its longest word fits, but not below 10 px", () => {
    expect(cardFont("Аренка", 150)).toBe(12);
    expect(cardFont("Дерадикон", 74)).toBe(11);
    expect(cardFont("Дерадикон", 40)).toBe(10);
  });

  it("cuts only a word that does not fit even then, with «…»; the others stay whole", () => {
    const measure = (text: string) => text.length * 6; // 6 px a letter
    expect(fitName("Ру / Астерия", 16 + 42, measure)).toBe("Ру / Астерия"); // 7 letters = 42 px fit
    expect(fitName("Дерадикон", 16 + 42, measure)).toBe("Деради…"); // 6 letters and «…» = 42 px
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

  it("the ribbon is a magnifier: the 4 hours around now take the middle 60 %, the 8 hours at each side the 20 %", () => {
    const H = 3_600_000;
    expect(ribbonX(0)).toBe(0.5);
    expect(ribbonX(-4 * H)).toBeCloseTo(0.2);
    expect(ribbonX(4 * H)).toBeCloseTo(0.8);
    expect(ribbonX(12 * H)).toBeCloseTo(1);
    expect(ribbonX(-12 * H)).toBeCloseTo(0);
    expect(ribbonX(30 * H)).toBe(1); // outside the ribbon: held at its edge
    expect(ribbonX(H) - ribbonX(0)).toBeCloseTo(3 * (ribbonX(9 * H) - ribbonX(8 * H))); // an hour in the middle is 3× wider
  });

  it("writes the countdown", () => {
    expect([0, 59 * 60000, 60 * 60000, 107 * 60000, 29 * 3600000, 50 * 3600000].map(countdown))
      .toEqual(["0 мин", "59 мин", "1 ч", "1 ч 47 мин", "1 д 5 ч", "2 дн"]);
  });
});
