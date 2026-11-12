// The one game database of Pulse+ (data/pulse.db, docs/ADR-002-pulse-db.md) as the screens reach it: `all(sql, params)`
// answers reading queries. In the program Rust reads the file on disk (db_query: nothing is loaded into the window);
// on the dev page a worker opens it with sql.js. The repositories of launcher/src/core/db take this `all`.
import { invoke } from "@tauri-apps/api/core";

import type { All } from "../../core/db/npcPoints";
import { readSchema, type SchemaState } from "../../core/db/schema";
import { platform } from "../platform";

function tauriAll(): All {
  return async (sql, params = []) => {
    const answer = await invoke<{ columns: string[]; rows: unknown[][] }>("db_query", { sql, params });
    return answer.rows.map((row) => Object.fromEntries(answer.columns.map((name, i) => [name, row[i]])));
  };
}

// only on the dev page: in the program's build the condition is a constant, so ./devDb (the worker and sql.js, 0.7 MB) is left out of it
const workerAll = async (): Promise<All | null> => (import.meta.env.DEV ? (await import("./devDb")).workerAll() : null);

let opened: Promise<All | null> | null = null;

/** The database's reading query, opened once; null when there is no data/pulse.db (the screens then use the old files). */
export function pulseDb(): Promise<All | null> {
  opened ??= (async () => {
    const all = platform === null ? await workerAll() : tauriAll();
    if (!all) return null;
    await all("SELECT 1 FROM npc LIMIT 1"); // there and readable, or the error below
    return all;
  })().catch((error) => { console.warn("pulse.db", error); return null; });
  return opened;
}

let version: Promise<SchemaState> | null = null;

/** Whether the database on disk is the one this program was written for (core/db/schema.ts), asked once. */
export function pulseDbSchema(): Promise<SchemaState> {
  version ??= pulseDb().then((all) => (all ? readSchema(all) : { found: null, fits: false, text: "База игры не найдена: нет файла data/pulse.db." }));
  return version;
}
