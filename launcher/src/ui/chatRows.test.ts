import { describe, expect, it } from "vitest";

import { WatchSession } from "../core/chat/session";
import { channelLabel, makeRows, shown } from "./chatRows";

const LINES = [
  "2026.10.22 20:00:01 : [3.Поиск группы] [charname:Morgrim;1 1 1]: wts [item:110600968;ver2;;;] 2kk",
  "2026.10.22 20:00:02 : [1.Общий] [charname:Kaelith;1.0000 1.0000 1.0000]: всем привет",
  "2026.10.22 20:00:03 : [charname:Pyro;0.6275 1.0000 0.6275] шепчет: продам дёшево",
  "2026.10.22 20:00:04 : Вы получили 100 кинар.",
  "2026.10.22 20:00:05 : Бешеный ветер I: Скор. движ. цели Mockoco увеличивается.",
  "2026.10.22 20:00:06 : [2.Торговля] [charname:Tr;1 1 1]: wts всё",
  "2026.10.22 20:00:07 : [3.Поиск группы] [charname:Morgrim;1 1 1]: wts [item:110600968;ver2;;;] 2kk",
  "без времени",
];

describe("chat feed rows", () => {
  it("give every line a row, attach the session's matches and filter as Pulse's «Весь чат»", () => {
    const session = new WatchSession({ "110600968": "Кираса Рудры" }, {}, {}, { keywords: ["wts"], cooldownSec: 0 });
    const batch = session.process(LINES, 0);
    let key = 0;
    const rows = makeRows(LINES, batch.entries, () => ++key, {}, {}, {});
    expect(rows.map((r) => r.key)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(rows.map((r) => r.entry !== null)).toEqual([true, false, false, false, false, false, true]); // both LFG lines
    expect(rows.map((r) => r.category)).toEqual(["Поиск группы", "Общий", "Личное", null, null, null, "Поиск группы"]);
    expect(rows.map((r) => r.notice)).toEqual([false, false, false, true, false, false, false]);
    const visible = (mode: "matches" | "all", system: boolean) => rows.filter((r) => shown(r, mode, system)).map((r) => r.key);
    expect(visible("matches", true)).toEqual([1, 7]);
    expect(visible("all", false)).toEqual([1, 2, 3, 7]); // trade and combat lines never, notices only with «Система»
    expect(visible("all", true)).toEqual([1, 2, 3, 4, 7]);
    expect(rows.map(channelLabel)).toEqual(["3.Поиск группы", "Общий", "Личное", null, null, "2.Торговля", "3.Поиск группы"]);
  });
});
