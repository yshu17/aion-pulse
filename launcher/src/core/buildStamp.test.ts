import { describe, expect, it } from "vitest";
import { stampText } from "./buildStamp";

describe("build stamp", () => {
  it("shows the date, time and machine", () => {
    expect(stampText("2026-11-24T01:40", "laptop")).toBe("Сборка: 24.11.2026 01:40 · ноутбук");
    expect(stampText("2026-11-24T21:05:33", "PC")).toBe("Сборка: 24.11.2026 21:05 · ПК");
  });
  it("keeps an unknown machine name as it is and drops an empty one", () => {
    expect(stampText("2026-11-24T01:40", "desk-2")).toBe("Сборка: 24.11.2026 01:40 · desk-2");
    expect(stampText("2026-11-24T01:40", "")).toBe("Сборка: 24.11.2026 01:40");
  });
  it("is empty without a stamp", () => {
    expect(stampText(undefined, "pc")).toBe("");
    expect(stampText("вчера", "pc")).toBe("");
  });
});
