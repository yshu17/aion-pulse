/**
 * Read lines appended to a growing log file — the port of core/chat/tailer.py.
 *
 * The file is reached through a small reader (`size()` and `read(position, length)`), so Tauri, Node or a test can
 * give it. A missing file is the reader's error (it is passed on). Lines are bytes until decoded: UTF-8 when valid,
 * else CP1251 (the game's old encoding); a UTF-8 BOM is dropped.
 */

export const MAX_LINE_BYTES = 64 * 1024; // a longer line is dropped; chat lines are a few hundred bytes

export interface LogReader {
  size(): number;
  read(position: number, length: number): Uint8Array;
}

const UTF8 = new TextDecoder("utf-8", { fatal: true });
const CP1251 = new TextDecoder("windows-1251");

/** Decode one line: UTF-8 (without its BOM), else CP1251 where the unused byte 0x98 reads as «�», as in Python. */
export function decodeLine(line: Uint8Array): string {
  const bytes = line[0] === 0xef && line[1] === 0xbb && line[2] === 0xbf ? line.subarray(3) : line;
  try {
    return UTF8.decode(bytes);
  } catch {
    return CP1251.decode(bytes).replace(/\u0098/g, "�");
  }
}

/** Naive time of a log line («2026.10.20 18:00:00 : …») as milliseconds, or null (no time, impossible date). */
export function lineTime(line: Uint8Array): number | null {
  const head = String.fromCharCode(...line.subarray(0, 19));
  const m = /^(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}):(\d{2})/.exec(head);
  if (m === null) return null;
  const [y, mo, d, h, mi, s] = m.slice(1).map(Number);
  if (y < 1 || mo < 1 || mo > 12 || h > 23 || mi > 59 || s > 59 || d < 1) return null; // as Python's datetime()
  const days = [31, leap(y) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1];
  if (d > days) return null;
  return naiveMs(y, mo, d, h, mi, s);
}

const leap = (y: number) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;

/** A naive wall-clock time as milliseconds (no time zone: compared only with other naive times). */
export function naiveMs(y: number, mo: number, d: number, h = 0, mi = 0, s = 0): number {
  const date = new Date(Date.UTC(2000, mo - 1, d, h, mi, s));
  date.setUTCFullYear(y);
  return date.getTime();
}

function splitLines(data: Uint8Array): Uint8Array[] {
  const parts: Uint8Array[] = [];
  let start = 0;
  for (let i = 0; i < data.length; i++) {
    if (data[i] === 0x0a) {
      parts.push(data.subarray(start, i));
      start = i + 1;
    }
  }
  parts.push(data.subarray(start));
  return parts;
}

function rstripCr(line: Uint8Array): Uint8Array {
  let end = line.length;
  while (end > 0 && line[end - 1] === 0x0d) end--;
  return line.subarray(0, end);
}

function concat(a: Uint8Array, b: Uint8Array): Uint8Array {
  const out = new Uint8Array(a.length + b.length);
  out.set(a);
  out.set(b, a.length);
  return out;
}

export class LogTailer {
  droppedLines = 0;
  private pos = 0;
  private buf = new Uint8Array(0);
  private skipping = false; // inside a dropped over-long line: discard bytes up to its newline

  constructor(private reader: LogReader) {}

  /** Skip everything already in the file. */
  startAtEnd(): void {
    this.pos = this.reader.size();
    this.buf = new Uint8Array(0);
    this.skipping = false;
  }

  /** Complete lines appended since the last call; a file shorter than our position was recreated. */
  readNewLines(): string[] {
    const size = this.reader.size();
    if (size < this.pos) {
      this.pos = 0;
      this.buf = new Uint8Array(0);
      this.skipping = false;
    }
    if (size === this.pos) return [];
    let data = this.reader.read(this.pos, size - this.pos);
    this.pos += data.length;
    if (this.skipping) {
      const nl = data.indexOf(0x0a);
      if (nl < 0) return [];
      data = data.subarray(nl + 1);
      this.skipping = false;
    }
    const parts = splitLines(concat(this.buf, data));
    this.buf = parts.pop()!.slice();
    if (this.buf.length > MAX_LINE_BYTES) {
      this.droppedLines += 1;
      this.buf = new Uint8Array(0);
      this.skipping = true;
    }
    return parts.map((line) => decodeLine(rstripCr(line)));
  }

  /** Complete lines before the current position whose time is >= since, reading backwards in chunks. */
  readBacklog(since: number, chunkSize = 256 * 1024): string[] {
    const end = this.pos;
    let start = end;
    while (start > 0) {
      start = Math.max(0, start - chunkSize);
      let lines = splitLines(this.reader.read(start, end - start));
      if (start > 0) lines = lines.slice(1); // the first piece may be a partial line
      const first = lines.map(lineTime).find((t) => t !== null);
      if (first !== undefined && first !== null && first < since) break;
    }
    let lines = splitLines(this.reader.read(start, end - start));
    if (start > 0) lines = lines.slice(1);
    const result: string[] = [];
    for (const raw of lines.slice(0, -1)) { // the piece after the last newline is not a complete line
      const line = rstripCr(raw);
      const time = lineTime(line);
      if (time !== null && time >= since) result.push(decodeLine(line));
    }
    return result;
  }
}
