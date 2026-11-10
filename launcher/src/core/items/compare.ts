/**
 * Two item cards side by side: which stats of one are better or worse than the other's. Pure: blocks in, marks out.
 *
 *   compareStats(blocks, other) -> { "Атака": "up", "Точность": "dn", … }   the marks of `blocks` against `other`
 *
 * A value is the number(s) of its text («250-340» is 295, «+19%» is 19, «2.4» is 2.4); only labels both cards have
 * are compared. A bigger number is better except for the stats where less is faster (the attack's time).
 */

import type { Block } from "./card";

export type Mark = "up" | "dn";

/** Less is better: the attack's time in seconds. */
const LESS_IS_BETTER = new Set(["Скор. атаки", "Время каста", "Время применения", "Откат"]);

/** The number a stat's text stands for, or null («—», words). */
export function statNumber(text: string): number | null {
  const plain = String(text).replace(/\s/g, "").replace(",", ".");
  const range = /^(\d+(?:\.\d+)?)[-–](\d+(?:\.\d+)?)/.exec(plain);
  if (range) return (Number(range[1]) + Number(range[2])) / 2;
  const number = /[+-]?\d+(?:\.\d+)?/.exec(plain);
  return number ? Number(number[0]) : null;
}

/** Every label → number of the stat blocks (pairs and grids) of a card; the first of a repeated label. */
export function stats(blocks: Block[]): Map<string, number> {
  const out = new Map<string, number>();
  for (const block of blocks) {
    const rows = block.kind === "pairs" ? block.rows : block.kind === "grid" ? block.pairs : null;
    for (const [label, value] of (rows as [string, string][] | null) ?? []) {
      const n = statNumber(value);
      if (n !== null && !out.has(label)) out.set(label, n);
    }
  }
  return out;
}

export function compareStats(blocks: Block[], other: Block[]): Record<string, Mark> {
  const mine = stats(blocks);
  const theirs = stats(other);
  const marks: Record<string, Mark> = {};
  for (const [label, value] of mine) {
    const them = theirs.get(label);
    if (them === undefined || them === value) continue;
    const better = LESS_IS_BETTER.has(label) ? value < them : value > them;
    marks[label] = better ? "up" : "dn";
  }
  return marks;
}
