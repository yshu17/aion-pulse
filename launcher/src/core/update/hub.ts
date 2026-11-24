/**
 * One place for «what can be updated»: the program (a newer release) and the game data (a newer db pack).
 *
 *   pending(app, db)            -> Pending: what is on offer now (null = nothing)
 *   pendingKey(p)               -> "v2.3.2|2026-11-24" — identifies this set of updates, «Позже» is remembered per key
 *   isPostponed(p, stored)      -> true when the user already said «Позже» to exactly this set
 *   announceText(p)             -> the sentence of the bottom notice
 *   installOrder(p)             -> ["db", "app"] subset: the data first, the program last (it restarts the program)
 *   allLabel(p)                 -> label of the joint button: «Обновить всё» when both, otherwise the one thing
 */

export interface AppPart { tag: string }
export interface DbPart { built: string; size: number }
export interface Pending { app: AppPart | null; db: DbPart | null }

export type Part = "db" | "app";

export const pending = (app: AppPart | null, db: DbPart | null): Pending | null => (app || db ? { app, db } : null);

export const pendingKey = (p: Pending): string => `${p.app?.tag ?? ""}|${p.db?.built.slice(0, 10) ?? ""}`;

export const isPostponed = (p: Pending, stored: string): boolean => stored !== "" && stored === pendingKey(p);

export function announceText(p: Pending): string {
  if (p.app && p.db) return `Вышло обновление программы ${p.app.tag} и новые данные игры.`;
  if (p.app) return `Вышла новая версия программы ${p.app.tag}.`;
  return "Есть новые данные игры: предметы, задания, NPC.";
}

export const installOrder = (p: Pending): Part[] => [...(p.db ? ["db" as const] : []), ...(p.app ? ["app" as const] : [])];

export const allLabel = (p: Pending): string => (p.app && p.db ? "Обновить всё" : p.app ? "Обновить программу" : "Обновить данные");
