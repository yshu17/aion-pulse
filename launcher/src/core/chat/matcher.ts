/**
 * Keyword search over chat messages, with an anti-spam cooldown — the port of core/chat/matcher.py.
 */

import type { ChatMessage } from "./parser";

const PURGE_THRESHOLD = 1000;
/** How keyword hits and watched-item hits combine. */
export const MODES = ["or", "words", "items", "and"];

/** Lower case and «ё» as «е». Keeps the string length. */
export function normalize(text: string): string {
  return text.toLowerCase().replace(/ё/g, "е");
}

export class Matcher {
  mode = "or";
  private keywordPairs: [string, string][] = [];
  private watch = new Map<string, string>();
  private seen = new Map<string, number>(); // nick + text -> time of the last hit

  constructor(keywords: string[], public cooldown_sec = 60, watchItems: Record<string, string> = {}, mode = "or") {
    this.setMode(mode);
    this.setKeywords(keywords);
    this.setWatchItems(watchItems);
  }

  /** «or» word or item, «words» only words, «items» only items, «and» word and item. */
  setMode(mode: string): void {
    this.mode = MODES.includes(mode) ? mode : "or";
  }

  /** Item id -> display name. A message linking any of these ids matches. */
  setWatchItems(watchItems: Record<string, string>): void {
    this.watch = new Map(Object.entries(watchItems));
  }

  get keywords(): string[] {
    return this.keywordPairs.map(([original]) => original);
  }

  setKeywords(keywords: string[]): void {
    const result: [string, string][] = [];
    const seen = new Set<string>();
    for (const keyword of keywords) {
      const original = keyword.trim();
      const norm = normalize(original);
      if (norm && !seen.has(norm)) {
        seen.add(norm);
        result.push([original, norm]);
      }
    }
    this.keywordPairs = result;
  }

  /** The number of remembered (nick, text) pairs (for tests of the purge). */
  get seenSize(): number {
    return this.seen.size;
  }

  /** Matched keywords and watched item names, combined by the mode; [] if nothing or a recent repeat. */
  check(msg: ChatMessage, now: number): string[] {
    const text = normalize(msg.text);
    const words = this.keywordPairs.filter(([, norm]) => text.includes(norm)).map(([original]) => original);
    const items: string[] = [];
    for (const id of new Set(msg.item_ids)) {
      const name = this.watch.get(id);
      if (name !== undefined && !items.includes(name)) items.push(name);
    }
    let hits: string[];
    if (this.mode === "words") hits = words;
    else if (this.mode === "items") hits = items;
    else if (this.mode === "and") hits = words.length && items.length ? [...words, ...items] : [];
    else hits = [...words, ...items.filter((name) => !words.includes(name))];
    if (!hits.length) return [];
    const key = `${msg.nick}\u0000${text}`;
    const last = this.seen.get(key);
    if (last !== undefined && now - last < this.cooldown_sec) return [];
    if (this.seen.size >= PURGE_THRESHOLD) {
      this.seen = new Map([...this.seen].filter(([, t]) => now - t < this.cooldown_sec));
    }
    this.seen.set(key, now); // like a Python dict, a key set again keeps its first position
    return hits;
  }
}

/** Split text into [chunk, isMatch] pieces for highlighting. */
export function highlightSegments(text: string, keywords: string[]): [string, boolean][] {
  const norm = normalize(text);
  const marks = new Array<boolean>(text.length).fill(false);
  for (const keyword of keywords) {
    const needle = normalize(keyword.trim());
    if (!needle) continue;
    let start = norm.indexOf(needle);
    while (start !== -1) {
      for (let i = start; i < Math.min(start + needle.length, text.length); i++) marks[i] = true;
      start = norm.indexOf(needle, start + 1);
    }
  }
  const segments: [string, boolean][] = [];
  for (let i = 0; i < text.length; i++) {
    const last = segments[segments.length - 1];
    if (last && last[1] === marks[i]) last[0] += text[i];
    else segments.push([text[i], marks[i]]);
  }
  return segments;
}
