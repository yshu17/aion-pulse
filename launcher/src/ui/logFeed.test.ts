// The async feed of the screens must give what the core's synchronous LogFeed gives on the same file.
import { appendFileSync, closeSync, mkdtempSync, openSync, readSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { LogFeed } from "../core/chat/session";
import { LogReader, naiveMs } from "../core/chat/tailer";
import { AsyncLogFeed } from "./logFeed";

function stamp(h: number, m: number, s: number) {
  const p = (n: number) => String(n).padStart(2, "0");
  return `2026.10.22 ${p(h)}:${p(m)}:${p(s)}`;
}
const line = (h: number, m: number, s: number, text: string) => `${stamp(h, m, s)} : [3.Поиск группы] [charname:Nick;1 1 1]: ${text}\r\n`;

function enoent(path: string): Error & { code: string } {
  return Object.assign(new Error(`ENOENT: ${path}`), { code: "ENOENT" });
}

function syncReader(path: string): LogReader {
  return {
    size: () => { try { return statSync(path).size; } catch { throw enoent(path); } },
    read: (position, length) => {
      const fd = openSync(path, "r");
      try {
        const buffer = Buffer.alloc(length);
        const n = readSync(fd, buffer, 0, length, position);
        return new Uint8Array(buffer.subarray(0, n));
      } finally { closeSync(fd); }
    },
  };
}

function asyncFile(path: string) {
  const sync = syncReader(path);
  return { size: async () => sync.size(), read: async (position: number, length: number) => sync.read(position, length) };
}

describe("async log feed", () => {
  it("matches the core's LogFeed: history, new lines, a half line, a recreated and a missing file", async () => {
    const dir = mkdtempSync(join(tmpdir(), "feed-"));
    const path = join(dir, "Chat.log");
    const clock = () => naiveMs(2026, 10, 22, 20, 0, 0);
    try {
      writeFileSync(path, line(18, 0, 0, "старое") + line(19, 10, 0, "в истории") + line(19, 50, 0, "тоже в истории"));
      const a = new LogFeed(() => syncReader(path), 60, clock);
      const b = new AsyncLogFeed(asyncFile(path), 60, clock);
      const both = async () => [a.poll(), await b.poll()];

      let [x, y] = await both();
      expect(y).toEqual(x);
      expect(x[0]).toHaveLength(2);

      appendFileSync(path, line(20, 0, 5, "новая") + line(20, 0, 6, "ещё") + "2026.10.22 20:00:07 : [3.Поиск");
      [x, y] = await both();
      expect(y).toEqual(x);
      expect(x[1]).toHaveLength(2);

      appendFileSync(path, " группы] [charname:Nick;1 1 1]: хвост\r\n");
      [x, y] = await both();
      expect(y).toEqual(x);
      expect(x[1]).toHaveLength(1);

      [x, y] = await both(); // nothing new
      expect(y).toEqual(x);
      expect(x[1]).toEqual([]);

      writeFileSync(path, line(20, 5, 0, "после пересоздания")); // shorter than before: the file was recreated
      [x, y] = await both();
      expect(y).toEqual(x);
      expect(x[1]).toHaveLength(1);

      rmSync(path);
      await expect(b.poll()).rejects.toMatchObject({ code: "ENOENT" });
      expect(() => a.poll()).toThrow();
      writeFileSync(path, line(19, 59, 0, "вернулся") + line(20, 0, 1, "новая после возврата"));
      [x, y] = await both(); // the next poll starts over at the end of the file: no second history, nothing old
      expect(y).toEqual(x);
      expect(x).toEqual([null, []]);
      appendFileSync(path, line(20, 0, 9, "после возврата"));
      [x, y] = await both();
      expect(y).toEqual(x);
      expect(x[1]).toHaveLength(1);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("reads only the tail when the file is large", async () => {
    const asked: [number, number][] = [];
    const big = 6 * 1024 * 1024;
    const file = {
      size: async () => big,
      read: async (position: number, length: number) => { asked.push([position, length]); return new Uint8Array(length); },
    };
    const feed = new AsyncLogFeed(file, 60, () => naiveMs(2026, 10, 22, 20, 0, 0));
    await feed.poll();
    expect(asked).toEqual([[big - 4 * 1024 * 1024, 4 * 1024 * 1024]]);
  });
});
