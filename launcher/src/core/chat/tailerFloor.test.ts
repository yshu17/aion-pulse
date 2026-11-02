import { describe, expect, it } from "vitest";

import { LogReader, LogTailer, naiveMs } from "./tailer";

const stamp = (s: number) => `2026.11.01 19:${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

/** A log of `count` lines, one a second from 19:00:00, and a reader that remembers the lowest position it was asked for. */
function logOf(count: number) {
  const text = Array.from({ length: count }, (_, i) => `${stamp(i)} : [3.Поиск группы] [charname:Nick;1 1 1]: line ${i}\r\n`).join("");
  const bytes = new TextEncoder().encode(text);
  const seen = { lowest: Infinity, calls: 0 };
  const reader: LogReader = {
    size: () => bytes.length,
    read: (position, length) => {
      seen.calls++;
      seen.lowest = Math.min(seen.lowest, position);
      return bytes.slice(position, position + length);
    },
  };
  return { bytes, reader, seen };
}

describe("backlog of a dense log", () => {
  it("never reads below the floor, even when the whole range is newer than `since`", () => {
    const { bytes, reader, seen } = logOf(50);
    const tailer = new LogTailer(reader);
    tailer.startAtEnd();
    const floor = Math.floor(bytes.length / 2);
    // `since` is long before the first line: without a floor the walk goes back to the start of the file
    const lines = tailer.readBacklog(naiveMs(2026, 11, 1, 18, 0, 0), 64, floor);
    expect(seen.lowest).toBeGreaterThanOrEqual(floor);
    expect(lines.length).toBeGreaterThan(5);
    expect(lines.length).toBeLessThan(50); // only the lines of the half it may read
    expect(lines.every((l) => l.includes("line "))).toBe(true);
    expect(lines.at(-1)).toContain("line 49"); // the file ends with a newline: the last line is complete
  });

  it("without a floor it still walks back to the start, as before", () => {
    const { reader } = logOf(50);
    const tailer = new LogTailer(reader);
    tailer.startAtEnd();
    expect(tailer.readBacklog(naiveMs(2026, 11, 1, 18, 0, 0), 64)).toHaveLength(50);
  });
});
