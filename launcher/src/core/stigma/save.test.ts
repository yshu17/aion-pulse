import { describe, expect, it } from "vitest";

import { defaultSaved, readSaved, writeSaved } from "./save";

describe("the stigma build kept between runs", () => {
  it("comes back as it was written", () => {
    const saved = { cls: "knight", faction: "asmodian" as const, level: 50, pick: { normal: ["a"], advanced: ["c"], levels: { a: 30, c: 45 } } };
    expect(readSaved(writeSaved(saved))).toEqual(saved);
  });

  it("falls back to the default on nothing, broken text or wrong values", () => {
    expect(readSaved(null)).toEqual(defaultSaved());
    expect(readSaved("{oops")).toEqual(defaultSaved());
    expect(readSaved(JSON.stringify({ cls: "bard", faction: "x", level: 99, pick: { normal: [1], advanced: "no" } })))
      .toEqual({ ...defaultSaved(), level: 55 });
  });
});
