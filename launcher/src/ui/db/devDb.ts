// The dev page's way to data/pulse.db (the program reads the file in Rust: pulseDb.ts). Loaded only when import.meta.env.DEV.
import type { All } from "../../core/db/npcPoints";

// the dev page only: the file comes from the dev server (dropped from the program's build)
const devDb = import.meta.env.DEV
  ? import.meta.glob("../../../../data/pulse.db", { query: "?url", import: "default" }) as Record<string, () => Promise<string>>
  : {};

/** The database of the dev page: data/pulse.db from the dev server, opened by sql.js in a worker. */
export async function workerAll(): Promise<All | null> {
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
