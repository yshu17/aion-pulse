// The bestiary's database (data/bestiary/npcs.sqlite, tools/copy_bestiary_data.py) and its pictures (data/bestiary/icons).
// The file's bytes are read here (the program's file command is not in a worker) and handed to bestiaryWorker.ts, which
// opens them with sql.js and answers every search there: the page's thread only draws, typing never waits for the data.
import type { Row, SearchOptions } from "../../core/bestiary/store";
import { platform } from "../platform";

const CHUNK = 16 * 1024 * 1024; // one read of the program's file command

// the dev page only: the files come from the dev server (these lists are dropped from the program's build)
const devDb = import.meta.env.DEV
  ? import.meta.glob("../../../../data/bestiary/npcs.sqlite", { query: "?url", import: "default" }) as Record<string, () => Promise<string>>
  : {};
const devIcons = import.meta.env.DEV
  ? import.meta.glob("../../../../data/bestiary/icons/**/*.{png,jpg}", { query: "?url", import: "default" }) as Record<string, () => Promise<string>>
  : {};

let dataDir: Promise<string | null> | null = null;
/** data/bestiary next to data/maps (the program finds data/maps above its exe). */
function bestiaryDir(): Promise<string | null> {
  dataDir ??= (platform?.mapsDir() ?? Promise.resolve(null)).then((maps) => (maps ? maps.replace(/[\\/]maps$/, "\\bestiary") : null)).catch(() => null);
  return dataDir;
}

async function readFile(path: string): Promise<Uint8Array> {
  const size = await platform!.fileSize(path);
  const bytes = new Uint8Array(size);
  for (let at = 0; at < size; at += CHUNK) bytes.set(await platform!.readRange(path, at, Math.min(CHUNK, size - at)), at);
  return bytes;
}

async function databaseBytes(): Promise<ArrayBuffer | null> {
  if (platform === null) {
    const load = devDb["../../../../data/bestiary/npcs.sqlite"];
    return load ? (await fetch(await load())).arrayBuffer() : null;
  }
  const dir = await bestiaryDir();
  return dir ? (await readFile(`${dir}\\npcs.sqlite`)).buffer as ArrayBuffer : null;
}

/** The bestiary as the tab sees it: every call answers later; a search overtaken by a newer one answers null. */
export interface BestiaryClient {
  search(options: SearchOptions): Promise<[Row[], number] | null>;
  detail(npc: string): Promise<Row | null>;
  areas(npc: string): Promise<Row[]>;
}

function connect(worker: Worker): (message: Record<string, unknown>, transfer?: Transferable[]) => Promise<any> {
  let next = 1;
  const calls = new Map<number, { resolve(value: unknown): void; reject(error: Error): void }>();
  worker.onmessage = (event: MessageEvent<{ id: number; result?: unknown; error?: string; stale?: boolean }>) => {
    const { id, result, error, stale } = event.data;
    const call = calls.get(id);
    if (!call) return;
    calls.delete(id);
    if (error) call.reject(new Error(error));
    else call.resolve(stale ? null : result);
  };
  return (message, transfer = []) => new Promise((resolve, reject) => {
    const id = next++;
    calls.set(id, { resolve, reject });
    worker.postMessage({ ...message, id }, transfer);
  });
}

let client: Promise<BestiaryClient | null> | null = null;

/** The bestiary, opened once in its worker; null when the database is not there (a build without data/bestiary). */
export function openBestiary(): Promise<BestiaryClient | null> {
  client ??= (async () => {
    const bytes = await databaseBytes();
    if (!bytes) return null;
    const call = connect(new Worker(new URL("./bestiaryWorker.ts", import.meta.url), { type: "module" }));
    await call({ op: "open", bytes }, [bytes]); // the bytes move to the worker, no copy
    return {
      search: (options) => call({ op: "search", options }),
      detail: (npc) => call({ op: "detail", npc }),
      areas: (npc) => call({ op: "areas", npc }),
    } satisfies BestiaryClient;
  })().catch((error) => { console.error("bestiary", error); client = null; return null; });
  return client;
}

const icons = new Map<string, Promise<string | null>>();

/** The URL of a bestiary picture by its path in data/bestiary/icons («npc/icon_emblem_merchant.jpg»); null when missing. */
export function bestiaryIcon(path: string | null): Promise<string | null> {
  if (!path) return Promise.resolve(null);
  let url = icons.get(path);
  if (!url) {
    url = (async () => {
      if (platform === null) {
        const load = devIcons[`../../../../data/bestiary/icons/${path}`];
        return load ? await load() : null;
      }
      const dir = await bestiaryDir();
      if (!dir) return null;
      const bytes = await readFile(`${dir}\\icons\\${path.replace(/\//g, "\\")}`);
      return URL.createObjectURL(new Blob([bytes.slice()], { type: path.endsWith(".png") ? "image/png" : "image/jpeg" }));
    })().catch(() => null);
    icons.set(path, url);
  }
  return url;
}
