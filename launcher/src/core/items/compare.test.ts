import { describe, expect, it } from "vitest";

import { compareStats, statNumber, stats } from "./compare";

const bow = [
  { kind: "grid", pairs: [["Атака", "250-340"], ["Скор. атаки", "2.4"], ["Точность", "936"], ["Ф. крит.", "50"]] },
  { kind: "grid", pairs: [["Макс. HP", "+509"], ["Скорость атаки", "+19%"]] },
];
const epic = [
  { kind: "grid", pairs: [["Атака", "292-398"], ["Скор. атаки", "2.2"], ["Точность", "902"], ["Ф. крит.", "50"]] },
  { kind: "pairs", rows: [["Макс. HP", "+612"], ["Блок", "—"]] },
];

describe("comparing two item cards", () => {
  it("reads a stat's number: a range is its middle, signs and percents are dropped", () => {
    expect(statNumber("250-340")).toBe(295);
    expect(statNumber("+19%")).toBe(19);
    expect(statNumber("-1.6%")).toBe(-1.6);
    expect(statNumber("2,4")).toBe(2.4);
    expect(statNumber("—")).toBeNull();
    expect(stats(epic).has("Блок")).toBe(false);
  });

  it("marks the better and the worse stats; a shorter attack time is better; equal and lone stats get nothing", () => {
    expect(compareStats(epic, bow)).toEqual({ "Атака": "up", "Скор. атаки": "up", "Точность": "dn", "Макс. HP": "up" });
    expect(compareStats(bow, epic)).toEqual({ "Атака": "dn", "Скор. атаки": "dn", "Точность": "up", "Макс. HP": "dn" });
  });
});
