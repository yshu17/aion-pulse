// The bestiary's database (data/bestiary/npcs.sqlite, tools/copy_bestiary_data.py) opened in the page with sql.js, and
// its pictures (data/bestiary/icons). Read once, when the tab first needs them: about 45 MB go into memory.
import initSqlJs from "sql.js";
import wasmUrl from "sql.js/dist/sql-wasm.wasm?url";
import { inflate as pakoInflate } from "pako";

import { BestiaryStore, type Db, type Inflate } from "../../core/bestiary/store";
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

async function databaseBytes(): Promise<Uint8Array | null> {
  if (platform === null) {
    const load = devDb["../../../../data/bestiary/npcs.sqlite"];
    return load ? new Uint8Array(await (await fetch(await load())).arrayBuffer()) : null;
  }
  const dir = await bestiaryDir();
  return dir ? readFile(`${dir}\\npcs.sqlite`) : null;
}

const inflate: Inflate = (data, dictionary) => pakoInflate(data, dictionary ? { dictionary } : {});

let store: Promise<BestiaryStore | null> | null = null;

/** The store, opened once; null when the database is not there (a build without data/bestiary). */
export function openBestiary(): Promise<BestiaryStore | null> {
  store ??= (async () => {
    const [SQL, bytes] = await Promise.all([initSqlJs({ locateFile: () => wasmUrl }), databaseBytes()]);
    if (!bytes) return null;
    const sql = new SQL.Database(bytes);
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
    return new BestiaryStore(db, inflate);
  })().catch((error) => { console.error("bestiary", error); store = null; return null; });
  return store;
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
