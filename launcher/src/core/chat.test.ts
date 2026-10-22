// Step 3 of the port: core/chat replays the Python golden scenarios step by step.
import { appendFileSync, closeSync, mkdtempSync, openSync, readFileSync, readSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { category, isNotice } from "./chat/categories";
import { highlightSegments, Matcher, normalize } from "./chat/matcher";
import { ChatMessage, cleanText, displayText, isPlayer, parseAnyLine, parseLine, placesIn, splitPlace } from "./chat/parser";
import { messageSegments } from "./chat/segments";
import { SeriesTracker } from "./chat/series";
import { LogFeed, loudOf, WatchSession } from "./chat/session";
import { emptyFeed, errorStatus, gameOffNote, notFoundStatus, readErrorStatus, searchHint, statusChip, watchingStatus } from "./chat/status";
import { LogReader, LogTailer, naiveMs } from "./chat/tailer";
import { metresText, plural, splitKeywords } from "./text";

const ROOT = join(__dirname, "..", "..", "..");
const golden = (name: string) => JSON.parse(readFileSync(join(ROOT, "tests", "golden", `${name}.json`), "utf-8")).case;
const plain = (value: unknown) => JSON.parse(JSON.stringify(value));

const NAMES = { "110600968": "Кираса Рудры", "100000001": "Меч Циркулоса", "155007142": "Рецепт: клик", "186000163": "Монета" };
const MAPS = { "220070000": "Келькмарос", "210050000": "Ингисон" };
const QUESTS = { "2058": "Уничтожение повстанцев Ривара" };

function fileReader(path: string): LogReader {
  return {
    size: () => statSync(path).size,
    read: (position, length) => {
      const fd = openSync(path, "r");
      try {
        const out = new Uint8Array(length);
        const got = readSync(fd, out, 0, length, position);
        return out.subarray(0, got);
      } finally {
        closeSync(fd);
      }
    },
  };
}

const isoToNaive = (iso: string) => {
  const [d, t] = iso.split("T");
  const [y, mo, day] = d.split("-").map(Number);
  const [h, mi, s] = t.split(":").map(Number);
  return naiveMs(y, mo, day, h, mi, s);
};

describe("parser and categories", () => {
  const g = golden("chat_parser");
  it("every line parses as in Python", () => {
    for (const want of g.lines) {
      const line = want.line as string;
      const parsed = parseAnyLine(line, NAMES, MAPS, QUESTS);
      expect(plain(parsed), line).toEqual(want.any);
      expect(parsed === null ? null : isPlayer(parsed), line).toEqual(want.is_player);
      expect(plain(parseLine(line, NAMES, MAPS, QUESTS)), line).toEqual(want.lfg);
      expect(plain(parseAnyLine(line)), line).toEqual(want.bare);
      expect(parsed === null ? null : displayText(parsed.text), line).toEqual(want.display);
      expect(parsed === null ? null : plain(placesIn(parsed.text)), line).toEqual(want.places);
      expect(parsed === null ? null : category(parsed), line).toEqual(want.category);
      expect(parsed === null ? null : isNotice(parsed), line).toEqual(want.notice);
    }
  });
  it("clean text and place links", () => {
    for (const [text, bare, named] of g.clean) {
      expect(cleanText(text)).toBe(bare);
      expect(cleanText(text, { "2": "Меч Фланаса" }, MAPS, QUESTS)).toBe(named);
    }
    for (const [link, want] of g.split_place) expect(plain(splitPlace(link))).toEqual(want);
  });
});

describe("matcher", () => {
  const g = golden("chat_matcher");
  it("keeps cooldown and modes step by step", () => {
    const m = new Matcher([" WTS ", "ищу ГРУППУ", "", "wts", "ёлка"], 60, { "7": "Кираса Рудры" }, "or");
    expect(["keywords", m.keywords]).toEqual(g.steps[0]);
    for (const step of g.steps.slice(1)) {
      if (step[0] === "check") {
        const msg = step[1] as ChatMessage;
        expect(m.check(msg, step[2]), JSON.stringify(step)).toEqual(step[3]);
      } else if (step[0] === "mode") {
        m.setMode(step[1]);
        expect(m.mode).toBe(step[2]);
      } else if (step[0] === "items") {
        m.setWatchItems(step[1]);
      } else {
        m.setKeywords(step[1]);
        expect(m.keywords).toEqual(step[2]);
      }
    }
    const purge = new Matcher(["w"], 10);
    const msg = (nick: string): ChatMessage => ({ time: "2026.10.08 18:00:00", nick, text: "w", raw: "", item_ids: [] });
    for (let i = 0; i < 1001; i++) purge.check(msg(`N${i}`), i);
    expect([purge.check(msg("N0"), 1001), purge.check(msg("N1000"), 1001), purge.seenSize]).toEqual(g.purge);
    for (const [text, want] of g.normalize) expect(normalize(text)).toBe(want);
    for (const [text, keywords, want] of g.highlight) expect(highlightSegments(text, keywords)).toEqual(want);
  });
});

describe("repeat series", () => {
  const g = golden("chat_series");
  it("records, silences and accepts as in Python", () => {
    const t = new SeriesTracker(g.limit, g.idle_sec);
    const msg = (nick: string): ChatMessage => ({ time: "x", nick, text: "t", raw: "", item_ids: [] });
    for (const op of g.ops) {
      if (op[0] === "record") t.record(msg(op[1]), op[2], op[3], op[4]);
      else if (op[0] === "silent") expect(t.isSilent(msg(op[1]), op[2], op[3]), JSON.stringify(op)).toBe(op[4]);
      else if (op[0] === "accept") expect([...t.accept(op[1])].sort((a, b) => a - b)).toEqual(op[2]);
      else expect(SeriesTracker.keys(msg(op[1]), op[2])).toEqual(op[3]);
    }
  });
});

describe("watching session", () => {
  const g = golden("chat_session");
  it("replays the same batches, counters and alerts", () => {
    const init = g.init;
    const s = new WatchSession(NAMES, MAPS, QUESTS, { keywords: init.keywords, watchItems: init.watch_items,
      cooldownSec: init.cooldown_sec, alertMode: init.alert_mode, reactSec: init.react_sec });
    for (const op of g.ops) {
      const kind = op[0];
      const want = op[op.length - 1];
      const where = JSON.stringify(op.slice(0, -1));
      if (kind === "history" || kind === "process") {
        const batch = kind === "history" ? s.history(op[1], op[2]) : s.process(op[1], op[2]);
        expect(plain({ ...batch, loud: loudOf(batch) }), where).toEqual(want);
      } else if (kind === "state") {
        expect(plain({ counters: s.counters, pending: s.pendingIds, remaining: s.remaining(op[1]) }), where).toEqual(want);
      } else if (kind === "accept") expect(s.accept(op[1]), where).toEqual(want);
      else if (kind === "accept_all") expect(s.acceptAll(), where).toEqual(want);
      else if (kind === "expire") expect(s.expire(op[1]), where).toEqual(want);
      else if (kind === "mode") {
        s.setAlertMode(op[1]);
        expect(s.alertMode).toBe(want);
      } else if (kind === "stop") s.stop();
      else if (kind === "reset") s.resetCounters();
      else if (kind === "keywords") s.setKeywords(op[1]);
      else if (kind === "items") s.setWatchItems(op[1]);
    }
  });

  it("LogFeed: history once, then new lines; a missing file is passed on", () => {
    const dir = mkdtempSync(join(tmpdir(), "pulse-feed-"));
    const log = join(dir, "Chat.log");
    const now = naiveMs(2026, 10, 20, 18, 30);
    writeFileSync(log, Buffer.from("2026.10.20 17:00:00 : старое\r\n2026.10.20 18:25:00 : свежее\r\n", "utf-8"));
    const feed = new LogFeed(() => fileReader(log), 60, () => now);
    expect(feed.poll()).toEqual([["2026.10.20 18:25:00 : свежее"], []]);
    appendFileSync(log, Buffer.from("2026.10.20 18:31:00 : новое\r\n", "utf-8"));
    expect(feed.poll()).toEqual([null, ["2026.10.20 18:31:00 : новое"]]);
    const missing = new LogFeed(() => fileReader(join(dir, "none.log")), 0, () => now);
    expect(() => missing.poll()).toThrow();
  });
});

describe("message layout, status texts, text helpers", () => {
  const g = golden("chat_segments");
  it("segments", () => {
    const spec = { "Кираса Рудры": "110600968", "Меч Фланаса": "2" };
    const grades = { "110600968": "legend", "2": "nonsense" };
    for (const [text, hits, want] of g.segments) expect(plain(messageSegments(text, hits, spec, grades)), text).toEqual(want);
    for (const [text, hits, want] of g.segments_plain) expect(plain(messageSegments(text, hits)), text).toEqual(want);
  });
  it("status and empty feed", () => {
    for (const [text, want] of g.status_chip) expect(statusChip(text), text).toEqual(want);
    for (const [mode, keywords, items, hint, running, idle] of g.hints) {
      expect(searchHint(mode, keywords, items)).toBe(hint);
      expect(emptyFeed(true, mode, keywords, items)).toEqual(running);
      expect(emptyFeed(false, mode, keywords, items)).toEqual(idle);
    }
    expect([watchingStatus("C:/a", ""), watchingStatus("C:/a", "нет"), notFoundStatus("C:/b"), errorStatus("boom"),
      readErrorStatus("io"), gameOffNote("18:05")]).toEqual(g.texts);
  });
  it("plural, keywords, metres (Python rounding)", () => {
    for (const [n, want] of g.plural) expect(plural(n, "слово", "слова", "слов")).toBe(want);
    for (const [text, want] of g.split_keywords) expect(splitKeywords(text)).toEqual(want);
    for (const [metres, want] of g.metres) expect(metresText(metres), String(metres)).toBe(want);
  });
});

describe("log tail", () => {
  const g = golden("chat_tailer");
  it("replays the writes and reads the same lines", () => {
    const dir = mkdtempSync(join(tmpdir(), "pulse-tail-"));
    const log = join(dir, "Chat.log");
    const t = new LogTailer(fileReader(log));
    for (const op of g.ops) {
      if (op[0] === "write") writeFileSync(log, Buffer.from(op[1], "base64"));
      else if (op[0] === "append") appendFileSync(log, Buffer.from(op[1], "base64"));
      else if (op[0] === "start_at_end") t.startAtEnd();
      else expect(t.readNewLines(), JSON.stringify(op[0])).toEqual(op[op.length - 1]);
    }
  });
  it("reads the same backlog", () => {
    const dir = mkdtempSync(join(tmpdir(), "pulse-back-"));
    const log = join(dir, "Chat.log");
    writeFileSync(log, Buffer.from(g.backlog_file, "base64"));
    for (const [key, want] of Object.entries(g.backlog as Record<string, string[]>)) {
      const [since, chunk] = key.split("|");
      const t = new LogTailer(fileReader(log));
      t.startAtEnd();
      expect(t.readBacklog(isoToNaive(since), Number(chunk)), key).toEqual(want);
    }
  });
});
