/**
 * The stigma calculator's rules (github.com/Persepha/Aion-classic-stigma-calculator, pages/index.tsx and utils/slots_calc), as
 * data in, data out: which slots a level opens, the highest stigma level a character wears, the stigmas an advanced one needs
 * first, adding (with everything it needs), removing (with everything that needs it), keeping a pick valid when the level
 * changes, and the price in stigma shards and abyss points.
 *
 * A pick is two lists of stigma ids, the normal slots and the advanced ones, and the chosen level of each. A normal stigma goes
 * into a free advanced slot when the normal ones are full, as in the game.
 */

export type Faction = "elyos" | "asmodian";

export interface StigmaLevel {
  level: number;           // the character's level the stone needs
  skill: number;           // the client's skill id (pulse.db skill.id)
  name: string;
  text: string;
  mp: string;
  cast: string;
  cooldown: string;
  shards: number | null;   // null: not known (a level only pulse.db has)
  ap: number;
  price?: number | null;   // the stone's price in kinah, from pulse.db
  icon?: string;           // data/icons picture, from pulse.db
  stone?: number | null;   // the stone item's id, from pulse.db
  fromDb?: boolean;        // the level is not in the calculator's data
}

export interface Stigma {
  id: string;
  faction: string;         // daeva (both), elyos, asmodian
  advanced: boolean;
  kind: string;
  target: string;
  info: string[];
  levels: StigmaLevel[];
  onlyClient?: boolean;    // a stigma of pulse.db the calculator does not list
}

export interface Ctx {
  stigmas: Map<string, Stigma>;
  needs: [stigma: string, needs: string][];
  level: number;
}

export interface Pick {
  normal: string[];
  advanced: string[];
  levels: Record<string, number>;
}

export const MIN_LEVEL = 20;
export const MAX_LEVEL = 55;
const NORMAL_AT = [20, 20, 30, 40, 50, 55];
const ADVANCED_AT = [45, 45, 50, 52, 55];
export const SLOT_LEVELS = { normal: NORMAL_AT, advanced: ADVANCED_AT };

export const emptyPick = (): Pick => ({ normal: [], advanced: [], levels: {} });

export function slotsAt(level: number): { normal: number; advanced: number } {
  return { normal: NORMAL_AT.filter((at) => level >= at).length, advanced: ADVANCED_AT.filter((at) => level >= at).length };
}

/** The highest level of the stigma the character wears, or null when even the first is above it. */
export function bestLevel(stigma: Stigma, level: number): number | null {
  const fits = stigma.levels.map((l) => l.level).filter((l) => l <= level);
  return fits.length ? Math.max(...fits) : null;
}

/** Every stigma the given one needs first, the deepest first; the stigma itself is not in the list. */
export function needsOf(needs: Ctx["needs"], id: string): string[] {
  const out: string[] = [];
  const visit = (at: string) => {
    for (const [s, n] of needs) if (s === at && !out.includes(n)) { visit(n); if (!out.includes(n)) out.push(n); }
  };
  visit(id);
  return out;
}

/** Every stigma that needs the given one, directly or through others. */
export function dependantsOf(needs: Ctx["needs"], id: string): string[] {
  const out: string[] = [];
  const visit = (at: string) => {
    for (const [s, n] of needs) if (n === at && !out.includes(s)) { out.push(s); visit(s); }
  };
  visit(id);
  return out;
}

export const picked = (pick: Pick, id: string) => pick.normal.includes(id) || pick.advanced.includes(id);

/** What adding the stigma would put in: it and its needs not picked yet; null when one of them is above the character. */
function toAdd(ctx: Ctx, pick: Pick, id: string): string[] | null {
  if (picked(pick, id)) return null;
  const list = [...needsOf(ctx.needs, id), id].filter((x) => !picked(pick, x));
  for (const x of list) {
    const s = ctx.stigmas.get(x);
    if (!s || bestLevel(s, ctx.level) === null) return null;
  }
  return list;
}

export function canAdd(ctx: Ctx, pick: Pick, id: string): boolean {
  const list = toAdd(ctx, pick, id);
  if (!list) return false;
  const slots = slotsAt(ctx.level);
  const advanced = list.filter((x) => ctx.stigmas.get(x)!.advanced).length;
  const freeAdvanced = slots.advanced - pick.advanced.length - advanced;
  return freeAdvanced >= 0 && list.length - advanced <= slots.normal - pick.normal.length + freeAdvanced;
}

/** The pick with the stigma and everything it needs; the same pick when it does not fit. */
export function add(ctx: Ctx, pick: Pick, id: string): Pick {
  if (!canAdd(ctx, pick, id)) return pick;
  const free = slotsAt(ctx.level).normal - pick.normal.length;
  const next: Pick = { normal: [...pick.normal], advanced: [...pick.advanced], levels: { ...pick.levels } };
  let normals = 0;
  for (const x of toAdd(ctx, pick, id)!) {
    const s = ctx.stigmas.get(x)!;
    if (!s.advanced && normals < free) { next.normal.push(x); normals++; } else next.advanced.push(x);
    next.levels[x] = bestLevel(s, ctx.level)!;
  }
  return next;
}

/** The pick without the stigma and without every stigma that needs it. */
export function remove(ctx: Ctx, pick: Pick, id: string): Pick {
  const gone = new Set([id, ...dependantsOf(ctx.needs, id)]);
  const levels = Object.fromEntries(Object.entries(pick.levels).filter(([x]) => !gone.has(x)));
  return { normal: pick.normal.filter((x) => !gone.has(x)), advanced: pick.advanced.filter((x) => !gone.has(x)), levels };
}

/** The pick built again at the context's level: what no longer fits drops out, a chosen level stays while the character has it. */
export function refit(ctx: Ctx, pick: Pick): Pick {
  let next = emptyPick();
  for (const id of [...pick.normal, ...pick.advanced]) if (!picked(next, id)) next = add(ctx, next, id);
  for (const id of Object.keys(next.levels)) {
    const chosen = pick.levels[id];
    const s = ctx.stigmas.get(id)!;
    if (chosen !== undefined && chosen <= ctx.level && s.levels.some((l) => l.level === chosen)) next.levels[id] = chosen;
  }
  return next;
}

/** One level of a picked stigma: the chosen one. */
export function levelOf(ctx: Ctx, pick: Pick, id: string): StigmaLevel | null {
  return ctx.stigmas.get(id)?.levels.find((l) => l.level === pick.levels[id]) ?? null;
}

export function cost(ctx: Ctx, pick: Pick): { shards: number; ap: number; unknown: boolean } {
  let shards = 0, ap = 0, unknown = false;
  for (const id of [...pick.normal, ...pick.advanced]) {
    const l = levelOf(ctx, pick, id);
    if (!l) continue;
    if (l.shards === null) unknown = true; else shards += l.shards;
    ap += l.ap;
  }
  return { shards, ap, unknown };
}
