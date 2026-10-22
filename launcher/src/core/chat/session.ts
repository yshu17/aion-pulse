/**
 * The watching session without a window: Chat.log lines in, matches, alerts and place pins out — the port of
 * core/chat/session.py.
 *
 *   const session = new WatchSession(itemNames, mapNames, questNames, {keywords, watchItems, mode, cooldownSec,
 *                                    alertMode, reactSec})
 *   const feed = new LogFeed(openReader, historyMin, clock)   // history once, then new lines
 *   session.history(lines, now) / session.process(lines, now) -> Batch
 *   session.accept(id) / acceptAll() / expire(now) / remaining(now)
 * `now` is a monotonic clock in seconds that the caller owns.
 */

import type { Place } from "../map/zones";
import { AlertTracker } from "./alerts";
import { Matcher } from "./matcher";
import { ChatMessage, displayText, parseLine, placesIn } from "./parser";
import { SeriesTracker } from "./series";
import { LogReader, LogTailer } from "./tailer";

export const HISTORY = "history";
export const LOUD = "loud";
export const QUIET = "quiet";
export const ALERT_MODES = ["standard", "nag"];

export interface Entry {
  msg: ChatMessage;
  hits: string[];
  kind: string; // HISTORY, LOUD or QUIET
  alert_id: number | null; // nag mode: the pending alert of a LOUD entry
}

export interface Batch {
  entries: Entry[];
  places: Place[];
  announce: number[]; // pending alert ids not announced in a notification yet
}

/** The loud entries of a batch as [message, hits]. */
export function loudOf(batch: Batch): [ChatMessage, string[]][] {
  return batch.entries.filter((e) => e.kind === LOUD).map((e) => [e.msg, e.hits]);
}

export interface SessionOptions {
  keywords?: string[];
  watchItems?: Record<string, string>;
  mode?: string;
  cooldownSec?: number;
  alertMode?: string;
  reactSec?: number;
}

export class WatchSession {
  matcher: Matcher;
  tracker: AlertTracker;
  series = new SeriesTracker();
  alertMode: string;
  private announced = new Set<number>();

  constructor(public itemNames: Record<string, string> = {}, public mapNames: Record<string, string> = {},
              public questNames: Record<string, string> = {}, options: SessionOptions = {}) {
    this.matcher = new Matcher(options.keywords ?? [], options.cooldownSec ?? 60, { ...(options.watchItems ?? {}) },
      options.mode ?? "or");
    this.tracker = new AlertTracker(options.reactSec ?? 30);
    this.alertMode = ALERT_MODES.includes(options.alertMode ?? "") ? options.alertMode! : "standard";
  }

  // --- settings -----------------------------------------------------------------------------
  setKeywords(keywords: string[]): void { this.matcher.setKeywords(keywords); }
  setWatchItems(watchItems: Record<string, string>): void { this.matcher.setWatchItems({ ...watchItems }); }
  setMode(mode: string): void { this.matcher.setMode(mode); }
  setAlertMode(mode: string): void { this.alertMode = ALERT_MODES.includes(mode) ? mode : "standard"; }

  // --- lines -----------------------------------------------------------------------------------
  parse(line: string): ChatMessage | null {
    return parseLine(line, this.itemNames, this.mapNames, this.questNames);
  }

  /** Lines from before Start: matches are listed, nothing rings and nothing is counted. */
  history(lines: string[], now: number): Batch {
    const batch: Batch = { entries: [], places: [], announce: [] };
    for (const msg of this.messages(lines, batch)) {
      const hits = this.matcher.check(msg, now);
      if (hits.length) batch.entries.push({ msg, hits, kind: HISTORY, alert_id: null });
    }
    return batch;
  }

  /** New lines: count the matches; in nag mode each waits for «Принять» unless its series is accepted. */
  process(lines: string[], now: number): Batch {
    const batch: Batch = { entries: [], places: [], announce: [] };
    const nag = this.alertMode === "nag";
    for (const msg of this.messages(lines, batch)) {
      const hits = this.matcher.check(msg, now);
      if (!hits.length) continue;
      if (!nag) {
        this.tracker.add(msg, hits, now, false);
        batch.entries.push({ msg, hits, kind: LOUD, alert_id: null });
      } else if (this.series.isSilent(msg, hits, now)) {
        this.tracker.add(msg, hits, now, false);
        this.series.record(msg, hits, now);
        batch.entries.push({ msg, hits, kind: QUIET, alert_id: null });
      } else {
        const id = this.tracker.add(msg, hits, now, true);
        this.series.record(msg, hits, now, id);
        batch.entries.push({ msg, hits, kind: LOUD, alert_id: id });
      }
    }
    if (loudOf(batch).length) {
      batch.announce = this.tracker.pendingIds.filter((id) => !this.announced.has(id));
      for (const id of batch.announce) this.announced.add(id);
    }
    return batch;
  }

  private *messages(lines: string[], batch: Batch): Generator<ChatMessage> {
    for (const line of lines) {
      const msg = this.parse(line);
      if (msg === null) continue;
      const note = `${msg.time.slice(11, 16)}  ${msg.nick}: ${displayText(msg.text)}`;
      for (const [label, [mapId, x, y]] of placesIn(msg.text)) batch.places.push({ map_id: mapId, x, y, label, note });
      yield msg;
    }
  }

  // --- alerts ------------------------------------------------------------------------------------
  /** Accept an alert and every other waiting alert of the same series; returns the ids really accepted. */
  accept(id: number): number[] {
    const others = [...this.series.accept(id)].sort((a, b) => a - b);
    return [id, ...others].filter((a) => this.tracker.accept(a));
  }

  acceptAll(): number[] {
    const accepted = this.tracker.acceptAll();
    for (const id of accepted) this.series.accept(id);
    return accepted;
  }

  expire(now: number): number[] { return this.tracker.expire(now); }
  remaining(now: number): Record<number, number> { return this.tracker.remaining(now); }
  get pendingIds(): number[] { return this.tracker.pendingIds; }
  /** [found, reacted, missed] of this run. */
  get counters(): [number, number, number] { return [this.tracker.found, this.tracker.reacted, this.tracker.missed]; }
  resetCounters(): void { this.tracker.reset(); }
  /** Stop: the repeat series start anew at the next Start. */
  stop(): void { this.series.reset(); }
}

/**
 * Chat.log reading for a session: the first poll gives the history of the last `historyMin` minutes, then only new
 * lines. `open()` gives a reader of the file; a missing file is its error, passed on, and the next poll starts over.
 * `clock()` is the naive wall-clock time in milliseconds (see tailer.naiveMs).
 */
export class LogFeed {
  private tailer: LogTailer | null = null;
  private historyPending: boolean;

  constructor(private open: () => LogReader, public historyMin = 0, private clock: () => number) {
    this.historyPending = historyMin > 0;
  }

  /** [history lines or null, new lines]. */
  poll(): [string[] | null, string[]] {
    let history: string[] | null = null;
    try {
      if (this.tailer === null) {
        const tailer = new LogTailer(this.open());
        tailer.startAtEnd();
        this.tailer = tailer;
        if (this.historyPending) {
          history = tailer.readBacklog(this.clock() - this.historyMin * 60_000);
          this.historyPending = false;
        }
      }
      return [history, this.tailer.readNewLines()];
    } catch (error) {
      if ((error as { code?: string }).code === "ENOENT") this.tailer = null;
      throw error;
    }
  }
}
