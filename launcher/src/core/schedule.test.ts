// Step 5 of the port: core/schedule replays the Python golden results (tools/golden_schedule.py).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { naiveMs } from "./chat/tailer";
import { MISSED_DAYS, missedEvents, missedText, ReminderPlanner, START_WINDOW_S } from "./schedule/reminderFlow";
import { dueReminders, isoformat, occurrencesBetween, ScheduleEvent, startsAt, weekStart } from "./schedule/reminders";
import { check, Custom, eventKey, parseText, toText } from "./schedule/scheduleCustom";
import {
  clockPair, DAY_SHORT, dayBlocks, dayLabel, eventsForDay, GROUPS, groupHidden, groupOf, groups, kindOf, kinds, mapFor,
  nextEvents, todayEvents, visible,
} from "./schedule/scheduleView";
import {
  bellKey, DAY_NAMES, DAYS_ORDER, DEFAULT_LEAD, endOf, fixedZone, leadLabel, LEADS, mskNow, parseEvents, timeRange, todayKey,
  toLocal, untilText, zoneName,
} from "./schedule/timing";

const ROOT = join(__dirname, "..", "..", "..");
const golden = (name: string) => JSON.parse(readFileSync(join(ROOT, "tests", "golden", `${name}.json`), "utf-8")).case;

type Parts = [number, number, number, number, number, number];
const dt = (p: Parts) => naiveMs(...p);
const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

describe("schedule timing", () => {
  const g = golden("schedule_timing");
  it("reads events, converts clocks and writes times as in Python", () => {
    for (const [text, want] of g.load) expect(parseEvents(text), String(text)).toEqual(want);
    for (const [utc, want] of g.msk_now) expect(isoformat(mskNow(dt(utc)))).toBe(want);
    for (const [n, z, want] of g.to_local) expect(isoformat(toLocal(dt(n), fixedZone(z))), `${n} ${z}`).toBe(want);
    for (const [e, s, want] of g.end_of) expect(isoformat(endOf(e, dt(s))), JSON.stringify([e, s])).toBe(want);
    for (const [s, e, n, want] of g.until) expect(untilText(dt(s), dt(e), dt(n)), JSON.stringify(n)).toBe(want);
    const msk = naiveMs(2026, 10, 22, 20, 0, 0);
    for (const [z, want] of g.zone_name) expect(zoneName(msk, fixedZone(z)), String(z)).toBe(want);
    const extra: ScheduleEvent[] = golden("schedule_reminders").events.slice(-7); // EXTRA of the generator
    expect(extra.map(bellKey)).toEqual(g.bell_key);
    for (const [m, want] of g.lead_label) expect(leadLabel(m)).toBe(want);
    expect(LEADS).toEqual(g.leads);
    for (const [s, z, want] of g.time_range) {
      expect(timeRange(dt(s), endOf(extra[0], dt(s)), fixedZone(z)), `${s} ${z}`).toBe(want);
    }
    for (const [n, want] of g.today_key) expect(todayKey(dt(n))).toBe(want);
    expect([DAY_NAMES, DAYS_ORDER, DEFAULT_LEAD]).toEqual([g.day_names, g.days_order, g.default_lead]);
  });
});

describe("schedule reminders", () => {
  const g = golden("schedule_reminders");
  const events: ScheduleEvent[] = g.events;
  it("find due and past occurrences as in Python", () => {
    for (const [e, want] of g.starts_at) expect(isoformat(startsAt(e, naiveMs(2026, 10, 19)))).toBe(want);
    for (const [n, want] of g.week_start) expect(isoformat(weekStart(dt(n)))).toBe(want);
    for (const [n, lead, want] of g.due) {
      const got = dueReminders(events, dt(n), lead, new Set()).map(([k, e, at]) => [k, e.name, isoformat(at)]);
      expect(got, `${n} ${lead}`).toEqual(want);
    }
    const [sent, rest] = g.due_sent;
    expect(dueReminders(events, naiveMs(2026, 10, 22, 19, 45), 15, new Set(sent)).map(([k]) => k)).toEqual(rest);
    expect(() => dueReminders(events, dt([2026, 10, 19, 0, 30, 0]), -1, new Set())).toThrow(g.error);
    for (const [a, b, want] of g.between) {
      expect(occurrencesBetween(events, dt(a), dt(b)).map(([e, at]) => [e.name, isoformat(at)]), `${a} ${b}`).toEqual(want);
    }
  });
});

describe("schedule view", () => {
  const g = golden("schedule_view");
  const events: ScheduleEvent[] = golden("schedule_reminders").events;
  const extra = events.slice(-7);
  it("lists, filters, groups and lays out days as in Python", () => {
    for (const day of DAYS) {
      expect(eventsForDay(events, day).map((e) => `${e.name} ${e.start}`), day).toEqual(g.by_day[day]);
      expect(dayBlocks(eventsForDay(events, day)).map(([e, s, en, lane]) => [e.name, s, en, lane]), day).toEqual(g.blocks[day]);
    }
    for (const [n, want] of g.today) expect(todayEvents(events, dt(n)).map((e) => e.name)).toEqual(want);
    const nexts = g.next.slice(0, -1);
    for (const [n, limit, want] of nexts) {
      expect(nextEvents(events, dt(n), limit).map(([e, at]) => [e.name, isoformat(at)]), `${n} ${limit}`).toEqual(want);
    }
    const [n0, l0, w0] = g.next[g.next.length - 1];
    expect(nextEvents(extra.slice(0, 1), dt(n0), l0).map(([e, at]) => [e.name, isoformat(at)])).toEqual(w0);
    expect(kinds(events)).toEqual(g.kinds);
    expect(extra.map(kindOf)).toEqual(g.kind_of);
    expect([visible(events, new Set(["Арены", "Рейд"])).length, visible(events, new Set()).length]).toEqual(g.visible);
    for (const [maps, side, want] of g.map_for) {
      const event = extra.find((e) => JSON.stringify(e.maps ?? null) === JSON.stringify(maps))!;
      expect(mapFor(event, side)).toBe(want);
    }
    expect([groups(events), groups(extra), groups([])]).toEqual(g.groups);
    expect(events.map((e) => [e.name, groupOf(e)])).toEqual(g.group_of);
    for (const [hidden, want] of g.group_hidden) expect(groupHidden(events, new Set(hidden)).map((e) => e.name)).toEqual(want);
    for (const [d, n, t, want] of g.day_label) expect(dayLabel(d, dt(n), dt(t)), `${d} ${n} ${t}`).toBe(want);
    for (const [u, z, want] of g.clock_pair) expect(clockPair(dt(u), fixedZone(z))).toEqual(want);
    expect([GROUPS, DAY_SHORT]).toEqual([g.group_names, g.day_short]);
  });
});

describe("reminder flow", () => {
  const g = golden("schedule_flow");
  it("announces each belled occurrence once and reports missed ones as in Python", () => {
    expect([MISSED_DAYS, START_WINDOW_S]).toEqual(g.consts);
    for (const [lead, tz, start, steps, want] of g.runs) {
      const planner = new ReminderPlanner();
      const out: unknown[] = [];
      for (let i = 0; i < steps; i++) {
        const now = dt(start) + 30_000 * i;
        for (const r of planner.due(g.belled, now, lead, fixedZone(tz))) {
          out.push([isoformat(now), r.key, r.title, r.text, r.event.name, isoformat(r.start), isoformat(r.end)]);
        }
      }
      expect(out, `${lead} ${tz}`).toEqual(want);
    }
    for (const [last, now, found, texts] of g.missed) {
      const missed = missedEvents(g.belled, last === null ? null : dt(last), dt(now));
      expect(missed.map(([e, at]) => [e.name, isoformat(at)])).toEqual(found);
      expect([missedText(missed, fixedZone(180)), missedText(missed, fixedZone(-330)), missedText(missed, fixedZone(0), 2)])
        .toEqual(texts);
    }
    const capped = missedEvents(g.belled, naiveMs(2026, 9, 1), naiveMs(2026, 10, 22, 21, 30), 2);
    expect(capped.map(([e, at]) => [e.name, isoformat(at)])).toEqual(g.max_days);
  });
});

describe("own schedule events", () => {
  const g = golden("schedule_edits");
  const base: ScheduleEvent[] = golden("schedule_reminders").events;
  it("adds, hides, edits, saves and loads as in Python", () => {
    let file = "";
    const c = Custom.load(null, (text) => { file = text; });
    for (const [name, args, wantFile, wantTail, wantCount] of g.ops) {
      if (name === "add") c.add(args[0]);
      else if (name === "add_days") c.addDays(args[0], args[1]);
      else if (name === "remove") c.remove(args[0]);
      else c.edit(args[0], args[1]);
      const merged = c.merge(base);
      expect(file, name).toBe(wantFile);
      expect(merged.slice(-6).map((e) => [e.day, e.start, e.name, e.kind ?? null]), name).toEqual(wantTail);
      expect(merged.length).toBe(wantCount);
    }
    const nopath = new Custom(null);
    nopath.add({ day: "sat", start: "10:00", end: "11:00", name: "x" });
    expect(nopath.data).toEqual(g.nopath);
    for (const [text, want] of g.loads) expect(Custom.load(text, null).data, String(text)).toEqual(want);
    for (const [e, want] of g.checks) expect(check(e), JSON.stringify(e)).toBe(want);
    expect(base.slice(-7).map(eventKey)).toEqual(g.keys);
    expect([toText(base.slice(-7)), toText(base.slice(0, 12)), toText([])]).toEqual(g.to_text);
    for (const [text, events, problems] of g.parse) expect(parseText(text), JSON.stringify(text)).toEqual([events, problems]);
  });
});
