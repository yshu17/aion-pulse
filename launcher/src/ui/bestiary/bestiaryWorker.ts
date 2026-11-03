// The bestiary's database in a worker: sql.js parses the 45 MB file and runs every search here, off the page's thread,
// so typing in the tab never waits for it. Messages: open (the file's bytes), search, detail, areas; each answer carries
// the request's id. Searches that came in while another one ran are dropped for the newest one (answered as stale).
import initSqlJs from "sql.js";
import wasmUrl from "sql.js/dist/sql-wasm.wasm?url";
import { inflate as pakoInflate } from "pako";

import { BestiaryStore, type Db, type Inflate, type SearchOptions } from "../../core/bestiary/store";

type Request =
  | { id: number; op: "open"; bytes: ArrayBuffer }
  | { id: number; op: "search"; options: SearchOptions }
  | { id: number; op: "detail" | "areas"; npc: string };

const inflate: Inflate = (data, dictionary) => pakoInflate(data, dictionary ? { dictionary } : {});
let store: BestiaryStore | null = null;
let waiting: Extract<Request, { op: "search" }> | null = null; // the newest search not yet run
let scheduled = false;

const answer = (id: number, result: unknown) => postMessage({ id, result });
const fail = (id: number, error: unknown) => postMessage({ id, error: String(error) });

async function open(bytes: ArrayBuffer): Promise<void> {
  const SQL = await initSqlJs({ locateFile: () => wasmUrl });
  const sql = new SQL.Database(new Uint8Array(bytes));
  const db: Db = {
    all: (query, params = []) => {
      const statement = sql.prepare(query);
      try {
        statement.bind(params as any);
        const rows: Record<string, any>[] = [];
        while (statement.step()) rows.push(statement.getAsObject());
        return rows;
      } finally {
        statement.free();
      }
    },
    run: (query, params = []) => { sql.run(query, params as any); },
    func: (name, fn) => { sql.create_function(name, fn as any); },
  };
  store = new BestiaryStore(db, inflate);
}

function runSearch(): void {
  scheduled = false;
  const request = waiting;
  waiting = null;
  if (!request) return;
  try {
    answer(request.id, store!.search(request.options));
  } catch (error) {
    fail(request.id, error);
  }
}

self.onmessage = async (event: MessageEvent<Request>) => {
  const request = event.data;
  try {
    if (request.op === "open") { await open(request.bytes); answer(request.id, true); return; }
    if (!store) throw new Error("the bestiary is not open");
    if (request.op === "search") {
      if (waiting) postMessage({ id: waiting.id, stale: true }); // a newer search replaces one that has not run
      waiting = request;
      if (!scheduled) { scheduled = true; setTimeout(runSearch, 0); }
      return;
    }
    answer(request.id, request.op === "detail" ? store.detail(request.npc) : store.areas(request.npc));
  } catch (error) {
    fail(request.id, error);
  }
};
