// pulse.db on the dev page only (a plain browser has no program to ask): sql.js opens the file's bytes in this worker and
// answers reading queries. The program itself asks Rust (db_query), which reads the file on disk.
import initSqlJs, { type Database } from "sql.js";
import wasmUrl from "sql.js/dist/sql-wasm.wasm?url";

type Request = { id: number; op: "open"; bytes: ArrayBuffer } | { id: number; op: "all"; sql: string; params: unknown[] };

let db: Database | null = null;

self.onmessage = async (event: MessageEvent<Request>) => {
  const request = event.data;
  try {
    if (request.op === "open") {
      const SQL = await initSqlJs({ locateFile: () => wasmUrl });
      db = new SQL.Database(new Uint8Array(request.bytes));
      postMessage({ id: request.id, result: true });
      return;
    }
    if (!db) throw new Error("pulse.db is not open");
    const statement = db.prepare(request.sql);
    try {
      statement.bind(request.params as any);
      const rows: Record<string, unknown>[] = [];
      while (statement.step()) rows.push(statement.getAsObject());
      postMessage({ id: request.id, result: rows });
    } finally {
      statement.free();
    }
  } catch (error) {
    postMessage({ id: request.id, error: String(error) });
  }
};
