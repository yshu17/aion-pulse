import { describe, expect, it } from "vitest";

import { allWanted, builtText, packRows, selectedSize, summaryText } from "./dataPacks";

const db = (over = {}) => ({ available: false, size: 22_000_000, built: "2026-11-24T20:27:25Z", current: "2026-11-24T20:27:25Z", can_install: true, error: "", ...over });
const maps = (over = {}) => ({ needed: false, installed: true, size: 146_000_000, ...over });

describe("the data packs in the settings", () => {
  it("say what is installed, what has a newer pack and what is missing", () => {
    expect(packRows(db(), maps()).map((r) => [r.id, r.state])).toEqual([["db", "ok"], ["maps", "ok"]]);
    expect(packRows(db({ available: true }), maps({ needed: true })).map((r) => r.state)).toEqual(["newer", "newer"]);
    expect(packRows(db(), maps({ needed: true, installed: false }))[1].state).toBe("missing");
  });

  it("say when the database release did not answer and when this copy cannot download", () => {
    expect(packRows(db({ error: "no network", built: "" }), maps())[0].state).toBe("unknown");
    expect(packRows(db({ available: true, can_install: false }), maps()).map((r) => r.state)).toEqual(["fixed", "ok"]);
  });

  it("say in words why a row cannot be chosen, and sum up the section", () => {
    const fixed = packRows(db({ available: true, can_install: false }), maps({ size: 0 }));
    expect(fixed[0].note).toContain("эта копия берёт базу из своей папки");
    expect(summaryText(fixed)).toBe("Эта копия базу не скачивает: это делает Pulse+.exe.");
    expect(summaryText(packRows(db(), maps()))).toBe("Всё установлено.");
    expect(summaryText(packRows(db({ error: "x" }), maps()))).toBe("GitHub не ответил: проверь интернет.");
    expect(summaryText(packRows(db({ available: true }), maps()))).toBe("");
  });

  it("count only what would be downloaded", () => {
    const rows = packRows(db({ available: true }), maps({ needed: true }));
    expect(allWanted(rows)).toEqual(["db", "maps"]);
    expect(selectedSize(rows, ["maps"])).toBe(146_000_000);
    expect(selectedSize(rows, ["db", "maps"])).toBe(168_000_000);
    expect(allWanted(packRows(db(), maps()))).toEqual([]);
  });

  it("write the built time of a pack as a date and a time", () => {
    expect(builtText("2026-11-24T20:27:25Z")).toMatch(/^24\.11\.2026 \d\d:27$/);
    expect(builtText("")).toBe("");
  });
});
