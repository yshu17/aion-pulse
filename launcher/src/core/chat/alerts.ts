/** Alert bookkeeping: found / reacted / missed counters and pending alerts — the port of core/chat/alerts.py. */

import type { ChatMessage } from "./parser";

interface Alert {
  id: number;
  msg: ChatMessage;
  hits: string[];
  created: number;
}

export class AlertTracker {
  found = 0;
  reacted = 0;
  missed = 0;
  private pending = new Map<number, Alert>();
  private nextId = 1;

  constructor(public react_sec = 30) {} // 0 = wait for the user forever

  get pendingIds(): number[] {
    return [...this.pending.keys()];
  }

  /** Count a match. In nag mode it stays pending until accepted or expired. */
  add(msg: ChatMessage, hits: string[], now: number, nag: boolean): number {
    const id = this.nextId++;
    this.found += 1;
    if (nag) this.pending.set(id, { id, msg, hits, created: now });
    return id;
  }

  accept(id: number): boolean {
    if (!this.pending.delete(id)) return false;
    this.reacted += 1;
    return true;
  }

  acceptAll(): number[] {
    const ids = this.pendingIds;
    for (const id of ids) this.accept(id);
    return ids;
  }

  /** Move alerts older than react_sec to «missed». Returns their ids. */
  expire(now: number): number[] {
    if (this.react_sec <= 0) return [];
    const overdue = [...this.pending.values()].filter((a) => now - a.created >= this.react_sec).map((a) => a.id);
    for (const id of overdue) {
      this.pending.delete(id);
      this.missed += 1;
    }
    return overdue;
  }

  /** Seconds left before each pending alert expires ({} when there is no timeout). */
  remaining(now: number): Record<number, number> {
    if (this.react_sec <= 0) return {};
    const out: Record<number, number> = {};
    for (const a of this.pending.values()) out[a.id] = this.react_sec - (now - a.created);
    return out;
  }

  /** Zero the counters. Pending alerts stay pending. */
  reset(): void {
    this.found = this.reacted = this.missed = 0;
  }
}
