/**
 * «Настройки → Данные»: the data packs of the releases the program can download (docs/TASKS_TG_2026-11-18.md, task 14:
 * the game database and the maps; other servers and older versions need a list of them in the releases). Pure.
 *
 *   packRows(dbStatus, mapsStatus) -> PackRow[]    dbStatus / mapsStatus: what Rust answers (db_pack_status, maps_status)
 *     state  ok       installed, nothing newer
 *            newer    a newer pack is on the release
 *            missing  not downloaded yet
 *            unknown  the release did not answer
 *            fixed    this copy cannot download it (not started from Pulse+.exe): the data comes with the program
 *   allWanted(rows) -> ids with something to download      selectedSize(rows, ids) -> bytes of those
 *   summaryText(rows) -> why there is nothing to download, «» when there is
 *   builtText("2026-11-24T20:27:25Z") -> "24.11.2026 21:27" (local time), «» for «»
 */
export type PackId = "db" | "maps";
export type PackState = "ok" | "newer" | "missing" | "unknown" | "fixed";
export interface PackRow { id: PackId; name: string; note: string; size: number; state: PackState }

export interface DbStatus { available: boolean; size: number; built: string; current: string; can_install: boolean; error: string }
export interface MapsState { needed: boolean; installed: boolean; size: number }

const two = (n: number) => String(n).padStart(2, "0");

export function builtText(built: string): string {
  const d = new Date(built);
  if (!built || Number.isNaN(d.getTime())) return "";
  return `${two(d.getDate())}.${two(d.getMonth() + 1)}.${d.getFullYear()} ${two(d.getHours())}:${two(d.getMinutes())}`;
}

export function packRows(db: DbStatus, maps: MapsState): PackRow[] {
  const have = builtText(db.current);
  const dbState: PackState = !db.can_install ? "fixed" : db.error ? "unknown" : db.available ? "newer" : "ok";
  const mapsState: PackState = maps.needed ? (maps.installed ? "newer" : "missing") : "ok";
  return [
    { id: "db", name: "База игры", size: dbState === "fixed" ? 0 : db.size, state: dbState,
      note: [have ? `стоит от ${have}` : "предметы, задания, NPC", dbState === "newer" ? `новая от ${builtText(db.built)}` : "",
        dbState === "fixed" ? "эта копия берёт базу из своей папки" : ""].filter(Boolean).join(" · ") },
    { id: "maps", name: "Карты", size: maps.size, state: mapsState, note: "все локации, рельеф и Бездна" },
  ];
}

export const allWanted = (rows: PackRow[]): PackId[] => rows.filter((r) => r.state === "newer" || r.state === "missing").map((r) => r.id);

export const selectedSize = (rows: PackRow[], ids: PackId[]): number =>
  rows.filter((r) => ids.includes(r.id) && (r.state === "newer" || r.state === "missing")).reduce((sum, r) => sum + r.size, 0);

/** The line under the packs when there is nothing to download; «» when there is. */
export function summaryText(rows: PackRow[]): string {
  if (allWanted(rows).length) return "";
  if (rows.some((r) => r.state === "unknown")) return "GitHub не ответил: проверь интернет.";
  if (rows.some((r) => r.state === "fixed")) return "Эта копия базу не скачивает: это делает Pulse+.exe.";
  return "Всё установлено.";
}
