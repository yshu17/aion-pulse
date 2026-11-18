/**
 * The plus of the schedule grid: where it stands under the pointer and what time a new event or reset there gets.
 * A day's events merge into busy blocks. Within EDGE_PX of a block's edge the plus stands on that edge (an hour before or
 * after the block); else in a free gap tall enough on the hour line nearest the pointer (an hour, up to the next block),
 * or, with no hour lines given, on the gap's middle (the gap's start, two hours at most).
 *
 *   busyBlocks(spans, yOf)          the day's [start, end] minutes merged, with their pixels (yOf: minute -> px)
 *   plusAt(blocks, y, height)       the spot for the pointer at y px, or null (inside a block, away from its edges)
 * Over a band of resets (Grid.tsx) the spot is "side": the plus stands at the right end, off the reset marks.
 */

export interface Block { s: number; e: number; top: number; bottom: number }
export interface PlusSpot { y: number; from: number; to: number; edge: "gap" | "before" | "after" | "side" }

export const EDGE_PX = 8;     // how near a block's edge the pointer brings the edge plus
export const GAP_PX = 24;     // a gap lower than this has no plus of its own (its edges do)
const GAP_MAX = 120;          // the longest event a gap's plus offers
const EDGE_LEN = 60;          // the event before or after a block

export function busyBlocks(spans: [number, number][], yOf: (minute: number, end?: boolean) => number): Block[] {
  const out: { s: number; e: number }[] = [];
  for (const [s, e] of [...spans].sort((a, b) => a[0] - b[0])) {
    const last = out[out.length - 1];
    if (last && s <= last.e) last.e = Math.max(last.e, e);
    else out.push({ s, e });
  }
  return out.map((b) => ({ ...b, top: yOf(b.s), bottom: yOf(b.e, true) }));
}

export interface HourLine { m: number; y: number }

export function plusAt(blocks: Block[], y: number, height: number, hours: HourLine[] = []): PlusSpot | null {
  // a block's edge under the pointer comes first: the event right before or after the block
  let best: PlusSpot | null = null;
  let distance = EDGE_PX + 1;
  for (const b of blocks) {
    const above = Math.abs(y - b.top);
    if (above < distance && b.s > 0) { distance = above; best = { y: b.top, from: Math.max(0, b.s - EDGE_LEN), to: b.s, edge: "before" }; }
    const below = Math.abs(y - b.bottom);
    if (below < distance && b.e < 1440) { distance = below; best = { y: b.bottom, from: b.e, to: Math.min(1440, b.e + EDGE_LEN), edge: "after" }; }
  }
  if (best) return best;
  // the free gaps: before the first block, between blocks, after the last
  let top = 0, from = 0;
  for (const b of [...blocks, { s: 1440, e: 1440, top: height, bottom: height }]) {
    if (y >= top && y <= b.top && b.top - top >= GAP_PX && b.s > from) {
      // on the hour line nearest the pointer inside the gap (it needs a quarter of an hour before the block); else the middle
      const lines = hours.filter((h) => h.y >= top && h.y <= b.top && h.m >= from && Math.min(h.m + 60, b.s) - h.m >= 15);
      const line = lines.sort((p, q) => Math.abs(p.y - y) - Math.abs(q.y - y))[0];
      if (line) return { y: line.y, from: line.m, to: Math.min(line.m + 60, b.s), edge: "gap" };
      return { y: (top + b.top) / 2, from, to: Math.min(b.s, from + GAP_MAX), edge: "gap" };
    }
    top = b.bottom;
    from = b.e;
  }
  return null;
}
