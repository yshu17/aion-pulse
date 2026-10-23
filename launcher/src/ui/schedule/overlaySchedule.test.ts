import { describe, expect, it } from "vitest";

import { ScheduleEvent } from "../../core/schedule/reminders";
import { overlaySchedule } from "./overlaySchedule";

const ev = (day: string, start: string, end: string, name: string): ScheduleEvent => ({ day, start, end, name, group: "Арены", color: "Зелёный" });
const at = (iso: string) => Date.parse(iso + "Z"); // naive MSK as ms

describe("overlay schedule", () => {
  const events = [ev("fri", "10:00", "12:00", "Дерадикон"), ev("fri", "11:00", "13:00", "Инга"), ev("fri", "14:00", "16:00", "Аренка"),
    ev("thu", "22:00", "02:00", "Ночь")];

  it("shows what runs now, ending soonest first, and what starts next", () => {
    const s = overlaySchedule(events, at("2026-10-23T11:22:00")); // a Friday
    expect(s.current.map((e) => [e.name, e.to, e.left])).toEqual([["Дерадикон", "12:00", "ещё 38 мин"], ["Инга", "13:00", "ещё 1 ч 38 мин"]]);
    expect([s.next?.name, s.next?.from, s.next?.left]).toEqual(["Аренка", "14:00", "через 2 ч 38 мин"]);
  });

  it("keeps an overnight event running after midnight", () => {
    const s = overlaySchedule(events, at("2026-10-23T01:00:00"));
    expect(s.current.map((e) => e.name)).toEqual(["Ночь"]);
    expect(s.next?.name).toBe("Дерадикон");
  });
});
