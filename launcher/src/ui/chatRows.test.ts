import { describe, expect, it } from "vitest";

import { WatchSession } from "../core/chat/session";
import { naiveMs } from "../core/chat/tailer";
import { channelLabel, historyMinutes, makeRows, pruneRows, rowMs, shown } from "./chatRows";

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


describe("old messages leave the feed", () => {
  const at = (h: number, m: number, s = 0) => naiveMs(2026, 10, 22, h, m, s);
  const lines = [
    "2026.10.22 20:00:00 : [3.Поиск группы] [charname:A;1 1 1]: первое",
    "2026.10.22 20:05:00 : [3.Поиск группы] [charname:B;1 1 1]: второе",
    "2026.10.22 20:09:30 : [3.Поиск группы] [charname:C;1 1 1]: третье",
    "строка без времени",
  ];
  const rows = () => { let key = 0; return makeRows(lines, [], () => ++key, {}, {}, {}); };

  it("reads the time of a row on the scale of the wall clock", () => {
    expect(rowMs(rows()[0])).toBe(at(20, 0));
    expect(rows()).toHaveLength(3); // a line without a time is no row at all
  });

  it("takes out what is older than the keep time and keeps the rest", () => {
    expect(pruneRows(rows(), at(20, 10), 10, () => false).map((r) => r.line.text)).toEqual(["первое", "второе", "третье"]); // exactly 10 min old: kept
    expect(pruneRows(rows(), at(20, 10, 1), 10, () => false).map((r) => r.line.text)).toEqual(["второе", "третье"]);
    expect(pruneRows(rows(), at(20, 20), 10, () => false)).toEqual([]);
  });

  it("keeps everything when the keep time is 0, and gives back the same array when nothing goes", () => {
    const all = rows();
    expect(pruneRows(all, at(23, 0), 0, () => false)).toBe(all);
    expect(pruneRows(all, at(20, 9, 40), 10, () => false)).toBe(all);
  });

  it("keeps a match that still waits for «Принять», however old", () => {
    const all = rows();
    const kept = pruneRows(all, at(21, 0), 10, (row) => row.line.text === "первое");
    expect(kept.map((r) => r.line.text)).toEqual(["первое"]);
  });

  it("reads no more history than the feed keeps", () => {
    expect(historyMinutes(0, 30, 10)).toBe(10);
    expect(historyMinutes(0, 5, 10)).toBe(5);
    expect(historyMinutes(20, 5, 10)).toBe(10);
    expect(historyMinutes(0, 30, 0)).toBe(30); // keep time 0: no limit
  });
});
