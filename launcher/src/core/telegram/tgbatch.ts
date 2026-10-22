/**
 * Packs chat lines into Telegram messages without going over the group rate limit — the port of
 * core/telegram/tgbatch.py.
 *
 * Telegram lets a bot post about 20 messages a minute to one group. The batcher:
 *   - normally sends 2 chat lines per Telegram message, as soon as the second line arrives;
 *   - switches to 4 lines per message once the last minute already holds `warnAt` (18) messages;
 *   - goes back to 2 lines when the last minute holds fewer than `relaxBelow` (10) messages;
 *   - never sends more than `limit` (20) messages in any 60 s window — lines wait in the queue;
 *   - sends a lone line after `flushAfter` seconds if no second line comes;
 *   - when the queue backs up (limit reached), packs more lines per message, up to 4096 characters,
 *     so nothing is lost and the queue catches up.
 * Pure logic, no network: the sender calls add() for new lines and poll() on every tick (`now` in seconds).
 *
 * Lengths count characters as Python does (an emoji is one character, not two UTF-16 units).
 */

export const TELEGRAM_MAX_CHARS = 4096;

export interface BatcherOptions {
  normal?: number;
  compact?: number;
  limit?: number;
  warnAt?: number;
  relaxBelow?: number;
  windowSec?: number;
  flushAfter?: number;
  maxChars?: number;
  maxQueue?: number;
}

/** Python len(): the number of code points. */
function charCount(text: string): number {
  let n = 0;
  for (let i = 0; i < text.length; i++) {
    const unit = text.charCodeAt(i);
    if (unit >= 0xd800 && unit <= 0xdbff && i + 1 < text.length) {
      const next = text.charCodeAt(i + 1);
      if (next >= 0xdc00 && next <= 0xdfff) i += 1;
    }
    n += 1;
  }
  return n;
}

/** Python text[:count]. */
function firstChars(text: string, count: number): string {
  return text.length <= count ? text : Array.from(text).slice(0, count).join("");
}

export class ChatBatcher {
  readonly normal: number;
  readonly compactSize: number;
  readonly limit: number;
  readonly warnAt: number;
  readonly relaxBelow: number;
  readonly windowSec: number;
  readonly flushAfter: number;
  readonly maxChars: number;
  readonly maxQueue: number;
  compact = false;
  dropped = 0; // lines lost because the queue was full
  private queue: [number, string][] = [];
  private sent: number[] = [];

  constructor(options: BatcherOptions = {}) {
    this.normal = options.normal ?? 2;
    this.compactSize = options.compact ?? 4;
    this.limit = options.limit ?? 20;
    this.warnAt = options.warnAt ?? 18;
    this.relaxBelow = options.relaxBelow ?? 10;
    this.windowSec = options.windowSec ?? 60.0;
    this.flushAfter = options.flushAfter ?? 3.0;
    this.maxChars = options.maxChars ?? TELEGRAM_MAX_CHARS;
    this.maxQueue = options.maxQueue ?? 500;
  }

  get batchSize(): number {
    return this.compact ? this.compactSize : this.normal;
  }

  get queued(): number {
    return this.queue.length;
  }

  sentLastWindow(now: number): number {
    this.prune(now);
    return this.sent.length;
  }

  add(line: string, now: number): void {
    if (this.queue.length >= this.maxQueue) {
      this.queue.shift();
      this.dropped += 1;
    }
    this.queue.push([now, line]);
  }

  /** Telegram messages to send right now (each is chat lines joined by newlines). */
  poll(now: number): string[] {
    const out: string[] = [];
    this.prune(now);
    this.updateMode();
    while (this.queue.length && this.sent.length < this.limit) {
      const size = this.batchSize;
      const oldest = this.queue[0][0];
      if (this.queue.length < size && now - oldest < this.flushAfter) break; // wait a little for more lines
      out.push(this.take(size, this.sent.length >= this.limit - 1));
      this.sent.push(now);
      this.updateMode();
    }
    return out;
  }

  /** Seconds until another message may be sent (0 if a slot is free). */
  nextSlotIn(now: number): number {
    this.prune(now);
    if (this.sent.length < this.limit) return 0.0;
    return Math.max(0.0, this.sent[0] + this.windowSec - now);
  }

  private prune(now: number): void {
    while (this.sent.length && now - this.sent[0] >= this.windowSec) this.sent.shift();
  }

  private updateMode(): void {
    const count = this.sent.length;
    if (count >= this.warnAt) this.compact = true;
    else if (count < this.relaxBelow) this.compact = false;
  }

  /** Join the next lines. The last free slot of the minute takes as many as fit maxChars characters. */
  private take(size: number, backlog: boolean): string {
    const lines: string[] = [];
    let length = 0;
    while (this.queue.length) {
      const line = firstChars(this.queue[0][1], this.maxChars);
      const extra = charCount(line) + (lines.length ? 1 : 0);
      if (lines.length && (length + extra > this.maxChars || (!backlog && lines.length >= size))) break;
      lines.push(line);
      length += extra;
      this.queue.shift();
    }
    return lines.join("\n");
  }
}
