// The bestiary's data for the tab: the one game database pulse.db (core/db/bestiary.ts; the program reads it with Rust,
// the dev page with sql.js, ui/db/pulseDb.ts) and the pictures of data/bestiary/icons.
import { areas, detail, search } from "../../core/db/bestiary";
import type { Row, SearchOptions } from "../../core/bestiary/store";
import { pulseDb } from "../db/pulseDb";
import { platform } from "../platform";

const CHUNK = 16 * 1024 * 1024; // one read of the program's file command

// the dev page only: the pictures come from the dev server (this list is dropped from the program's build)
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

/** The bestiary as the tab sees it: every call answers later (the tab drops answers a newer search has overtaken). */
export interface BestiaryClient {
  search(options: SearchOptions): Promise<[Row[], number] | null>;
  detail(npc: string): Promise<Row | null>;
  areas(npc: string): Promise<Row[]>;
}

let client: Promise<BestiaryClient | null> | null = null;

/** The bestiary over pulse.db, opened once; null when there is no database (a build without data/pulse.db). */
export function openBestiary(): Promise<BestiaryClient | null> {
  client ??= pulseDb().then((all) => all && {
    search: (options) => search(all, options),
    detail: (npc) => detail(all, npc),
    areas: (npc) => areas(all, npc),
  } satisfies BestiaryClient);
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
