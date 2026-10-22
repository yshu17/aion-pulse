/**
 * Repeat series for the nag mode: one player re-posting the same thing («1/12 … 11/12») — the port of
 * core/chat/series.py. A series is keyed by (nick, match). Every message of a series rings until the user accepts
 * one; after that the rest comes in silently. A series ends after `limit` messages, after `idle_sec` without a new
 * message, or on reset().
 */

import { normalize } from "./matcher";
import type { ChatMessage } from "./parser";

export const SERIES_LIMIT = 12;
export const SERIES_IDLE_SEC = 15 * 60;

interface Series {
  count: number;
  last: number;
  accepted: boolean;
  alertIds: Set<number>;
}

export class SeriesTracker {
  private series = new Map<string, Series>();

  constructor(public limit = SERIES_LIMIT, public idle_sec = SERIES_IDLE_SEC) {}

  static keys(msg: ChatMessage, hits: string[]): [string, string][] {
    const nick = msg.nick.trim().toLowerCase();
    const seen = new Set<string>();
    const out: [string, string][] = [];
    for (const hit of hits) {
      if (!hit.trim()) continue;
      const key: [string, string] = [nick, normalize(hit.trim())];
      const flat = key.join("\u0000");
      if (!seen.has(flat)) {
        seen.add(flat);
        out.push(key);
      }
    }
    return out;
  }

  /** True when every match of the message continues a series the user already accepted. */
  isSilent(msg: ChatMessage, hits: string[], now: number): boolean {
    const live = SeriesTracker.keys(msg, hits).map((key) => this.live(key, now));
    return live.length > 0 && live.every((s) => s !== null && s.accepted);
  }

  /** Add the message to its series (starting new ones where needed). */
  record(msg: ChatMessage, hits: string[], now: number, alertId: number | null = null): void {
    for (const key of SeriesTracker.keys(msg, hits)) {
      let s = this.live(key, now);
      if (s === null) {
        s = { count: 0, last: 0, accepted: false, alertIds: new Set() };
        this.series.set(key.join("\u0000"), s);
      }
      s.count += 1;
      s.last = now;
      if (alertId !== null) s.alertIds.add(alertId);
    }
  }

  /** Mark the series of an accepted alert as accepted. Returns the other alerts in them. */
  accept(alertId: number): Set<number> {
    const others = new Set<number>();
    for (const s of this.series.values()) {
      if (s.alertIds.has(alertId)) {
        s.accepted = true;
        for (const id of s.alertIds) others.add(id);
      }
    }
    others.delete(alertId);
    return others;
  }

  reset(): void {
    this.series.clear();
  }

  private live(key: [string, string], now: number): Series | null {
    const s = this.series.get(key.join("\u0000"));
    if (s === undefined || s.count >= this.limit || now - s.last >= this.idle_sec) return null;
    return s;
  }
}
