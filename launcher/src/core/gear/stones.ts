/**
 * The manastone picker's lists (the calculator, docs/concepts/gear-stones/stones.html). Pure.
 *
 *   stoneTabs(stones) -> string[]               the stats that have stones, in the order of the game's window
 *   stoneRows(stones, stat, best) -> StoneGroup[]  one stat's stones in groups by grade, the white ones first, then the green;
 *                                                   inside a group the highest level first. `best` keeps only the strongest stone(s) of the stat
 *                                                   (the highest number: «Атака +5», «Ф. крит. +17»), whatever its grade or level
 *   stoneSum(stones) -> [stat, value][]         what the chosen stones give together
 */

import type { Block } from "../items/card";
import type { Stone } from "./engine";

/** The order of the stat tabs: the ones a player looks for first; a stat not named here follows alphabetically. */
export const TAB_ORDER = ["phyattack", "magicalskillboost", "critical", "magicalhitaccuracy", "maxhp", "magicalresist", "block", "dodge", "parry",
  "hitaccuracy", "maxmp", "maxfp", "healskillboost"];
/** The grades in the order of the groups: white, then green (a stone's grade is «common» or «rare» in this version). */
export const GRADE_ORDER = ["common", "rare", "legend", "unique", "epic", "mythic"];

export interface StoneGroup { grade: string; rows: Stone[] }

export function stoneTabs(stones: Stone[]): string[] {
  const have = new Set(stones.map((s) => s.stat));
  const known = TAB_ORDER.filter((s) => have.has(s));
  return [...known, ...[...have].filter((s) => !TAB_ORDER.includes(s)).sort()];
}

export function stoneRows(stones: Stone[], stat: string, best = false): StoneGroup[] {
  let rows = stones.filter((s) => s.stat === stat);
  if (best && rows.length) {
    const top = Math.max(...rows.map((s) => s.value));
    rows = rows.filter((s) => s.value === top);
  }
  const rank = (g: string) => { const i = GRADE_ORDER.indexOf(g); return i < 0 ? GRADE_ORDER.length : i; };
  const grades = [...new Set(rows.map((s) => s.grade))].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
  return grades.map((grade) => ({ grade, rows: rows.filter((s) => s.grade === grade).sort((a, b) => b.level - a.level || b.value - a.value || a.id - b.id) }));
}

export function stoneSum(stones: (Stone | null)[]): [string, number][] {
  const sum = new Map<string, number>();
  for (const s of stones) if (s) sum.set(s.stat, (sum.get(s.stat) ?? 0) + s.value);
  return [...sum.entries()].sort((a, b) => TAB_ORDER.indexOf(a[0]) - TAB_ORDER.indexOf(b[0]) || a[0].localeCompare(b[0]));
}

/** The labels a card uses for a stone's stat, in the order they are tried (the game's card says «Физ. крит», the manastone «Ф. крит.»). */
export const CARD_LABELS: Record<string, string[]> = {
  phyattack: ["Физ. атака"], magicalskillboost: ["Сила магии"], critical: ["Физ. крит", "Ф. крит."], magicalhitaccuracy: ["Точн. маг.", "Маг. точность"],
  maxhp: ["Макс. HP"], magicalresist: ["Маг. сопр."], block: ["Блок щитом"], dodge: ["Уклонение"], parry: ["Парир.", "Парирование"],
  hitaccuracy: ["Точность"], maxmp: ["Макс. MP"], maxfp: ["Время полета", "Время полёта", "Макс. время полёта"], healskillboost: ["Сила исцеления"],
};

export type BonusGroup = "stone" | "enchant";
/** A number to show in a card: where it goes (labels the card may call the stat, whether a row without «+» is fine), how much, and whose it is. */
export interface BonusAdd { group: BonusGroup; labels: string[]; any: boolean; value: number }

/** The enchant's stats as a card names them. `any`: the item's own number («Атака 235-437», «Физ. защита 120») takes it, not only a «+» line. */
export const ENCHANT_LABELS: Record<string, { labels: string[]; any: boolean }> = {
  damage: { labels: ["Атака"], any: true }, magicalskillboost: { labels: ["Сила магии"], any: true },
  physicaldefend: { labels: ["Физ. защита"], any: true }, maxhp: { labels: ["Макс. HP"], any: false },
  physicalcriticalreducerate: { labels: ["Защ. от ф.крит."], any: false }, damagereduce: { labels: ["Снижение урона"], any: true },
  block: { labels: ["Блок щитом"], any: false },
};

/** What the chosen stones give, as numbers to place: always beside a «+» line (a stone's number is a bonus line of the card). */
export const stoneAdds = (sum: [string, number][]): BonusAdd[] =>
  sum.map(([stat, value]) => ({ group: "stone", labels: CARD_LABELS[stat] ?? [stat], any: false, value }));

/** What an enchant adds (core/gear/engine.ts enchantBonus), as numbers to place. */
export const enchantAdds = (bonus: Record<string, number>): BonusAdd[] =>
  Object.entries(bonus).filter(([, v]) => v).map(([stat, value]) => ({ group: "enchant", labels: ENCHANT_LABELS[stat]?.labels ?? [stat], any: ENCHANT_LABELS[stat]?.any ?? false, value }));

export interface BonusPlace {
  /** `${block index}:${row index}` -> the number added to that row (the enchant's and the stones' together). */
  deltas: Map<string, number>;
  /** The numbers the card has no row for: label, sum and whose, shown as blocks of their own. */
  extra: { group: BonusGroup; label: string; value: number }[];
  /** The block the extra rows go after: the last grid of «+» lines (or the one before the stones block), -1 when there are no extra rows. */
  after: number;
}

/**
 * Where the extra numbers go in a card: beside the first row of the stat's label (a «+» line; or the item's own number
 * when the number is the enchant's), the rest as extra rows after the last grid of «+» lines.
 */
export function placeBonus(blocks: Block[], adds: BonusAdd[]): BonusPlace {
  const deltas = new Map<string, number>();
  const extra: BonusPlace["extra"] = [];
  const plus = (v: unknown) => String(v).trim().startsWith("+");
  for (const add of adds) {
    let found = "";
    for (const label of add.labels) {
      for (let b = 0; b < blocks.length && !found; b++) {
        const rows = blocks[b].kind === "grid" ? (blocks[b].pairs as [string, string][]) : null;
        const at = rows ? rows.findIndex(([l, v]) => l === label && (add.any || plus(v))) : -1;
        if (at >= 0) found = `${b}:${at}`;
      }
      if (found) break;
    }
    if (found) { deltas.set(found, (deltas.get(found) ?? 0) + add.value); continue; }
    const label = add.labels[0] ?? "";
    const same = extra.find((e) => e.group === add.group && e.label === label);
    if (same) same.value += add.value; else extra.push({ group: add.group, label, value: add.value });
  }
  let after = -1;
  if (extra.length) {
    blocks.forEach((b, i) => { if (b.kind === "grid" && (b.pairs as [string, string][]).some(([, v]) => plus(v))) after = i; });
    if (after < 0) after = Math.max(0, blocks.findIndex((b) => b.kind === "stones") - 1);
  }
  return { deltas, extra, after };
}
