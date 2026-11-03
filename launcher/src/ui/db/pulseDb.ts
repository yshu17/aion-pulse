// The one game database of Pulse+ (data/pulse.db, docs/ADR-002-pulse-db.md) as the screens reach it: `all(sql, params)`
// answers reading queries. In the program Rust reads the file on disk (db_query: nothing is loaded into the window);
// on the dev page a worker opens it with sql.js. The repositories of launcher/src/core/db take this `all`.
import { invoke } from "@tauri-apps/api/core";

import type { All } from "../../core/db/npcPoints";
import { platform } from "../platform";

// the dev page only: the file comes from the dev server (dropped from the program's build)
const devDb = import.meta.env.DEV
  ? import.meta.glob("../../../../data/pulse.db", { query: "?url", import: "default" }) as Record<string, () => Promise<string>>
  : {};

function tauriAll(): All {
  return async (sql, params = []) => {
    const answer = await invoke<{ columns: string[]; rows: unknown[][] }>("db_query", { sql, params });
    return answer.rows.map((row) => Object.fromEntries(answer.columns.map((name, i) => [name, row[i]])));
  };
}

async function workerAll(): Promise<All | null> {
  const load = devDb["../../../../data/pulse.db"];
  if (!load) return null;
  const bytes = await (await fetch(await load())).arrayBuffer();
  const worker = new Worker(new URL("./dbWorker.ts", import.meta.url), { type: "module" });
  let next = 1;
  const calls = new Map<number, { resolve(v: any): void; reject(e: Error): void }>();
  worker.onmessage = (event: MessageEvent<{ id: number; result?: unknown; error?: string }>) => {
    const call = calls.get(event.data.id);
    if (!call) return;
    calls.delete(event.data.id);
    if (event.data.error) call.reject(new Error(event.data.error));
    else call.resolve(event.data.result);
  };
  const send = (message: Record<string, unknown>, transfer: Transferable[] = []) => new Promise<any>((resolve, reject) => {
    const id = next++;
    calls.set(id, { resolve, reject });
    worker.postMessage({ ...message, id }, transfer);
  });
  await send({ op: "open", bytes }, [bytes]);
  return (sql, params = []) => send({ op: "all", sql, params });
}

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
