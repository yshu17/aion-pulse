import { describe, expect, it } from "vitest";

import { allLabel, announceText, installOrder, isPostponed, pending, pendingKey } from "./hub";

const app = { tag: "v2.3.2" };
const db = { built: "2026-11-24T01:00:00", size: 17_000_000 };

describe("the update hub", () => {
  it("has nothing to show when nothing is on offer", () => {
    expect(pending(null, null)).toBeNull();
    expect(pending(app, null)).toEqual({ app, db: null });
  });

  it("installs the data before the program, because the program restarts", () => {
    expect(installOrder(pending(app, db)!)).toEqual(["db", "app"]);
    expect(installOrder(pending(app, null)!)).toEqual(["app"]);
    expect(installOrder(pending(null, db)!)).toEqual(["db"]);
  });

  it("remembers «Позже» for exactly this set of updates, a new one comes back", () => {
    const both = pending(app, db)!;
    expect(isPostponed(both, "")).toBe(false);
    expect(isPostponed(both, pendingKey(both))).toBe(true);
    expect(isPostponed(pending({ tag: "v2.3.3" }, db)!, pendingKey(both))).toBe(false);
    expect(isPostponed(pending(app, null)!, pendingKey(both))).toBe(false);
  });

  it("words the notice and the joint button for one or both updates", () => {
    expect(announceText(pending(app, db)!)).toContain("v2.3.2");
    expect(announceText(pending(app, db)!)).toContain("данные");
    expect(allLabel(pending(app, db)!)).toBe("Обновить всё");
    expect(allLabel(pending(app, null)!)).toBe("Обновить программу");
    expect(allLabel(pending(null, db)!)).toBe("Обновить данные");
  });
});
