/**
 * Background search for the Bestiary: a UI that types faster than the database answers never waits for it — the port
 * of core/bestiary/search_worker.py.
 *
 *     const worker = new SearchWorker(() => openStore());   // nothing opens until the first submit
 *     worker.submit(seq, { text, category: "monster", min_level: 10 });
 *     worker.latest() -> SearchResult | null                 // newest finished answer, older ones are dropped
 *
 * Python runs one thread; here the work runs on `schedule` (a macrotask by default), so a burst of submits made in the
 * same turn of the event loop collapses to the newest one, as requests queued behind a running search do in Python.
 */

import type { Row, SearchOptions } from "./store";

export interface SearchResult {
  seq: number;
  rows: Row[];
  total: number;
  error: string;
}

export interface SearchStore {
  search(options: SearchOptions): [Row[], number];
  close?(): void;
}

export class SearchWorker {
  private store: SearchStore | null = null;
  private failure = "";
  private opened = false;
  private pending: [number, SearchOptions] | null = null;
  private scheduled = false;
  private closed = false;
  private done: SearchResult[] = [];

  constructor(private factory: () => SearchStore,
              private schedule: (job: () => void) => void = (job) => { setTimeout(job, 0); }) {}

  submit(seq: number, options: SearchOptions = {}): void {
    if (this.closed) return;
    this.pending = [seq, options]; // a newer request replaces one that has not started
    if (!this.scheduled) {
      this.scheduled = true;
      this.schedule(() => this.run());
    }
  }

  /** The newest finished result, or null. Anything older that was waiting is discarded. */
  latest(): SearchResult | null {
    const result = this.done.length ? this.done[this.done.length - 1] : null;
    this.done = [];
    return result;
  }

  close(): void {
    this.closed = true;
    this.pending = null;
    this.store?.close?.();
    this.store = null;
  }

  private run(): void {
    this.scheduled = false;
    const job = this.pending;
    this.pending = null;
    if (job === null || this.closed) return;
    if (!this.opened) {
      this.opened = true;
      try {
        this.store = this.factory();
      } catch (error) {
        this.failure = error instanceof Error ? error.message : String(error);
      }
    }
    const [seq, options] = job;
    if (this.store === null) {
      this.done.push({ seq, rows: [], total: 0, error: this.failure });
      return;
    }
    try {
      const [rows, total] = this.store.search(options);
      this.done.push({ seq, rows, total, error: "" });
    } catch (error) {
      this.done.push({ seq, rows: [], total: 0, error: error instanceof Error ? error.message : String(error) });
    }
  }
}
