/**
 * The calculator's data file (data/stigma/classic24.json, tools/import_stigma_calc.py) for one class and faction, and the shape
 * of an advanced stigma tree: ten places on a 4×6 grid and the arrows between them, as the calculator draws it.
 */

import type { Faction } from "./calc";
import type { GitStigma } from "./merge";

export interface CalcData {
  source: { repo: string; commit: string; date: string; game: string };
  classes: Record<string, {
    stigmas: GitStigma[];
    trees: Record<Faction, string[][]>;
    needs: Record<Faction, [string, string][]>;
  }>;
}

/** A tree's places in the file's order (tier4_1, tier4_2, tier4_3, tier3_1, tier3_2, tier4_4, tier4_5, tier2_1, tier2_2, tier1): column and rows [from, to). */
export const PLACES: { col: number; rows: [number, number] }[] = [
  { col: 0, rows: [0, 1] }, { col: 0, rows: [1, 2] }, { col: 0, rows: [2, 3] },
  { col: 1, rows: [0, 2] }, { col: 1, rows: [2, 3] }, { col: 1, rows: [3, 5] }, { col: 1, rows: [5, 6] },
  { col: 2, rows: [0, 3] }, { col: 2, rows: [3, 6] },
  { col: 3, rows: [0, 6] },
];
const mid = (i: number) => (PLACES[i].rows[0] + PLACES[i].rows[1]) / 2;

/**
 * A tree's arrows, [the place needed, the place that needs it]: for every need of a place's stigma, from the place of the needed
 * one in the nearest earlier column (the closest by height when it stands twice there).
 */
export function treeEdges(tree: string[], needs: [string, string][]): [number, number][] {
  const out: [number, number][] = [];
  tree.forEach((id, to) => {
    for (const [s, n] of needs) {
      if (s !== id) continue;
      const from = tree.map((_, i) => i).filter((i) => tree[i] === n && PLACES[i].col < PLACES[to].col)
        .sort((a, b) => PLACES[b].col - PLACES[a].col || Math.abs(mid(a) - mid(to)) - Math.abs(mid(b) - mid(to)))[0];
      if (from !== undefined && !out.some(([a, b]) => a === from && b === to)) out.push([from, to]);
    }
  });
  return out;
}

/** One class for one faction: its stigmas (the faction's own and the shared), its two trees, its dependencies. */
export function classStigmas(data: CalcData, cls: string, faction: Faction) {
  const c = data.classes[cls];
  return {
    stigmas: c.stigmas.filter((s) => s.faction === "daeva" || s.faction === faction),
    trees: c.trees[faction],
    needs: c.needs[faction],
  };
}
