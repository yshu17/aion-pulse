/**
 * Read-only Bestiary data access — the port of core/bestiary/bestiary_store.py. Public API: search(), detail(),
 * areas(), races(), ranks(), zones(), regions(), coverage().
 *
 * The database (npcs.sqlite) is made by tools/build_bestiary_index.py. The store runs the same SQL as Python on a
 * database it is given (`Db`: node:sqlite in tests, sql.js or the Tauri side in the program) and inflates zlib blobs
 * with the given `inflate` (node:zlib, pako…). Python's collation «RU» (case-blind, «ё» as «е») becomes the SQL
 * function ru_key(), which the store registers: ORDER BY ru_key(x) sorts exactly as COLLATE RU did, since SQLite
 * compares the keys by code point like Python compares strings.
 */

import { casefold } from "../py";
import { FACTIONS } from "./labels";

export type Row = Record<string, any>;

export interface Db {
  all(sql: string, params?: unknown[]): Row[];
  run(sql: string, params?: unknown[]): void;
  /** Register a deterministic one-argument SQL function. */
  func(name: string, fn: (value: unknown) => unknown): void;
}

/** zlib inflate (with an optional preset dictionary). */
export type Inflate = (data: Uint8Array, dictionary?: Uint8Array) => Uint8Array;

const LINK_ID = /(?:pulse:\/\/npc\/|https?:\/\/kb\.aionempire\.com\/npc\/)(\d+)/i;

// Preset zlib dictionary for the per-NPC detail blobs: their keys and boilerplate repeat in every row.
const DETAIL_DICT = new TextEncoder().encode(
  '{"id":"","name":"","internal_name":"","category":"monster","role":"","title":"","description":"",'
  + '"stock":"","trade_tabs":[],"stock_source":"client_npcs.xml + client_npc_goodslist.xml + '
  + 'client_npc_trade_in_list.xml + client_items.xml","race":"","faction":"","kind":"","rank":"","level":"",'
  + '"hp_bar":null,"icon_asset":"","stats":{"Макс. ХП":"","Опыт":""},"drops":"","points":[{"mob_id":"",'
  + '"x":,"y":,"gx":,"gy":,"gz":,"source":"level","map_id":"2100"}],"kb_locations":[{"slug":"","name":"",'
  + '"count":}],"kb_url":"https://kb.aionempire.com/npc/","kb_status":"","seller_inventory_state":"",'
  + '"Монстр","Торговец","NPC","Элийцы","Асмодиане","Балауры","Другие","Обычный","Элитный","Герой","Легенда"',
);

const utf8 = new TextDecoder();

export function unpackDetail(blob: Uint8Array, inflate: Inflate): Row {
  return JSON.parse(utf8.decode(inflate(blob, DETAIL_DICT)));
}

export const LOW_LEVEL = 40; // monsters below this level have a group of their own
const LEVEL = "CASE WHEN n.level GLOB '[0-9]*' THEN CAST(n.level AS INTEGER) END";
export const ORDERS: Record<string, string> = {
  "": "n.has_profile DESC,n.point_count DESC,ru_key(n.name),n.id",
  level_asc: `${LEVEL} IS NULL,${LEVEL},ru_key(n.name),n.id`, // no level: at the end either way
  level_desc: `${LEVEL} IS NULL,${LEVEL} DESC,ru_key(n.name),n.id`,
  name_asc: "ru_key(n.name),n.id",
  name_desc: "ru_key(n.name) DESC,n.id",
};

/** Russian alphabetical order, case-blind, «ё» with «е» (the key of the RU collation). */
export function russianKey(text: string): string {
  return casefold(text).replace(/ё/g, "е");
}

export function unpackIds(blob: Uint8Array, inflate: Inflate): Set<number> {
  const out = new Set<number>();
  let value = 0;
  let shift = 0;
  let previous = 0;
  for (const byte of inflate(blob)) {
    value += (byte & 0x7f) * 2 ** shift; // not «<<»: rowids pass 2^31
    if (byte & 0x80) {
      shift += 7;
    } else {
      previous += value;
      out.add(previous);
      value = shift = 0;
    }
  }
  return out;
}

/** Case-insensitive text matching and in-app NPC links. */
export function searchKey(value: string): string {
  const text = value.trim();
  const link = LINK_ID.exec(text);
  return link ? link[1] : casefold(text);
}

export interface SearchOptions {
  text?: string;
  category?: string;
  race?: string;
  rank?: string;
  map_id?: string;
  offset?: number;
  limit?: number;
  min_level?: number | null;
  max_level?: number | null;
  region?: string;
  order?: string;
  hide_low?: boolean;
}

export class BestiaryStore {
  readonly version: number;

  constructor(private db: Db, private inflate: Inflate) {
    db.func("ru_key", (value) => (typeof value === "string" ? russianKey(value) : value));
    this.version = Number(db.all("PRAGMA user_version")[0].user_version);
    if (![1, 2, 3, 4, 5, 6, 7].includes(this.version)) throw new RangeError(`Неизвестный формат базы бестиария: ${this.version}`);
  }

  coverage(): [number, number, number] {
    const row = this.db.all("SELECT count(*) AS a,sum(has_profile) AS b,sum(level != '') AS c FROM npc")[0];
    return [Number(row.a ?? 0), Number(row.b ?? 0), Number(row.c ?? 0)];
  }

  races(): string[] {
    if (this.version >= 2) return [...FACTIONS];
    return this.db.all("SELECT race FROM npc WHERE race != '' GROUP BY race ORDER BY count(*) DESC, race").map((r) => r.race);
  }

  ranks(): string[] {
    return this.db.all("SELECT rank FROM npc WHERE rank != '' GROUP BY rank ORDER BY count(*) DESC, rank").map((r) => r.rank);
  }

  zones(): [string, string][] {
    return this.db.all("SELECT map_id,name FROM npc_zone GROUP BY map_id ORDER BY name,map_id").map((r) => [r.map_id, r.name]);
  }

  /**
   * order: "" (profiles and mobs with places first), level_asc, level_desc, name_asc, name_desc.
   * category "low": monsters below LOW_LEVEL; hide_low keeps them out of every other group.
   */
  search(options: SearchOptions = {}): [Row[], number] {
    const { text = "", category = "", race = "", rank = "", map_id = "", offset = 0, limit = 150, min_level = null,
      max_level = null, region = "", order = "", hide_low = false } = options;
    const clauses: string[] = [];
    const params: unknown[] = [];
    const term = searchKey(text);
    let droppedBy: [string, Set<number>][] = [];
    const byItem = Boolean(term) && !/^\p{Nd}+$/u.test(term);
    const soldSearch = ["merchant", ""].includes(category) && this.version >= 6 && byItem;
    const dropSearch = ["monster", ""].includes(category) && this.version >= 7 && byItem;
    const escaped = term.replace(/\\/g, "\\\\").replace(/%/g, "\\%").replace(/_/g, "\\_");
    if (term) {
      // The index also covers internal and localized names and the numeric ID; a merchant is also found by an item it
      // sells and a mob by an item it drops.
      const options = ["n.search_text LIKE ? ESCAPE '\\'"];
      params.push(`%${escaped}%`);
      if (soldSearch) {
        options.push("EXISTS (SELECT 1 FROM npc_stock s WHERE s.npc_id=n.id AND s.name LIKE ? ESCAPE '\\')");
        params.push(`%${escaped}%`);
      }
      if (dropSearch) {
        droppedBy = this.droppers(escaped);
        options.push("n.rowid IN (SELECT id FROM temp.hit)");
      }
      clauses.push("(" + options.join(" OR ") + ")");
    }
    if (this.version >= 5) { // technical and duplicate records are a group of their own
      clauses.push("n.service = ?");
      params.push(category === "service" ? 1 : 0);
    }
    const low = `(n.category = 'monster' AND n.level GLOB '[0-9]*' AND CAST(n.level AS INTEGER) < ${LOW_LEVEL})`;
    if (category === "low") clauses.push(low);
    else if (hide_low) clauses.push(`NOT ${low}`);
    if (category === "monster") clauses.push("n.category = 'monster'");
    else if (category === "npc") clauses.push("n.category = 'npc'");
    else if (category === "merchant") clauses.push("(n.role = 'merchant' OR n.kind = 'Торговец')");
    if (race) {
      clauses.push(this.version >= 2 && FACTIONS.includes(race) ? "n.faction = ?" : "n.race = ?");
      params.push(race);
    }
    if (rank) {
      clauses.push("n.rank = ?");
      params.push(rank);
    }
    if (map_id) {
      clauses.push("EXISTS (SELECT 1 FROM npc_zone z WHERE z.npc_id=n.id AND z.map_id=?)");
      params.push(map_id);
    }
    if (min_level !== null || max_level !== null) clauses.push("n.level != ''");
    if (min_level !== null) {
      clauses.push("CAST(n.level AS INTEGER) >= ?");
      params.push(min_level);
    }
    if (max_level !== null) {
      clauses.push("CAST(n.level AS INTEGER) <= ?");
      params.push(max_level);
    }
    if (region && this.version >= 3) {
      clauses.push("EXISTS (SELECT 1 FROM npc_region r WHERE r.npc_id=n.id AND r.name=?" + (map_id ? " AND r.map_id=?" : "") + ")");
      params.push(region);
      if (map_id) params.push(map_id);
    }
    const where = clauses.length ? " WHERE " + clauses.join(" AND ") : "";
    const total = Number(this.db.all("SELECT count(*) AS n FROM npc n" + where, params)[0].n);
    const found = this.db.all(
      "SELECT n.id,n.name,n.kind,n.race,n.rank,n.level,n.icon_asset,n.zone_names,"
      + (this.version >= 2 ? "n.faction," : "'' AS faction,")
      + "n.point_count,n.drop_count,n.has_profile FROM npc n" + where
      + " ORDER BY " + (ORDERS[order] ?? ORDERS[""]) + " LIMIT ? OFFSET ?",
      [...params, limit, offset],
    ).map((row) => ({ ...row }));
    const rowids = new Map<string, number>();
    if (dropSearch && found.length) {
      const marks = found.map(() => "?").join(",");
      for (const r of this.db.all(`SELECT id,rowid AS r FROM npc WHERE id IN (${marks})`, found.map((row) => row.id))) {
        rowids.set(r.id, Number(r.r));
      }
    }
    for (const row of found) { // the sold or dropped item that matched, shown on the card
      row.sold = row.dropped = "";
      if (!byItem || casefold(row.name).includes(term)) continue;
      if (soldSearch) {
        const hit = this.db.all(
          "SELECT shown FROM npc_stock WHERE npc_id=? AND name LIKE ? ESCAPE '\\' ORDER BY length(name) LIMIT 1",
          [row.id, `%${escaped}%`],
        )[0];
        row.sold = hit ? hit.shown : "";
      }
      if (dropSearch && !row.sold) {
        const number = rowids.get(row.id)!;
        row.dropped = droppedBy.find(([, numbers]) => numbers.has(number))?.[0] ?? "";
      }
    }
    return [found, total];
  }

  /** Items whose name contains the text, each with the rowids of the NPCs that drop it; fills temp.hit. */
  private droppers(escaped: string): [string, Set<number>][] {
    const found = this.db.all("SELECT name,npcs FROM item WHERE name_cf LIKE ? ESCAPE '\\' ORDER BY length(name)", [`%${escaped}%`])
      .map((row) => [row.name, unpackIds(row.npcs, this.inflate)] as [string, Set<number>]);
    this.db.run("CREATE TEMP TABLE IF NOT EXISTS hit (id INTEGER PRIMARY KEY)");
    this.db.run("DELETE FROM temp.hit");
    for (const [, ids] of found) for (const n of ids) this.db.run("INSERT OR IGNORE INTO temp.hit VALUES (?)", [n]);
    return found;
  }

  regions(mapId = ""): string[] {
    if (this.version < 3) return [];
    return this.db.all("SELECT DISTINCT name FROM npc_region" + (mapId ? " WHERE map_id=?" : "") + " ORDER BY name",
      mapId ? [mapId] : []).map((r) => r.name);
  }

  detail(npcId: string): Row | null {
    const row = this.db.all("SELECT detail FROM npc WHERE id=?", [String(npcId)])[0];
    if (!row) return null;
    const detail = unpackDetail(row.detail, this.inflate);
    if (this.version >= 4) { // drops are item ids; the item table holds name, rarity and icon once
      detail.drops = this.items(this.shared(detail.drops));
      detail.stock = this.shared(detail.stock);
    }
    return detail;
  }

  private shared(key: unknown): any[] {
    if (key === null || key === undefined || key === "" || (Array.isArray(key) && !key.length)) return [];
    if (typeof key !== "string") return key as any[];
    const row = this.db.all("SELECT data FROM shared WHERE key=?", [key])[0];
    return row ? JSON.parse(utf8.decode(this.inflate(row.data))) : [];
  }

  private items(ids: string[]): Row[] {
    const found = new Map<string, Row>();
    for (let start = 0; start < ids.length; start += 500) {
      const chunk = ids.slice(start, start + 500);
      const marks = chunk.map(() => "?").join(",");
      for (const row of this.db.all(`SELECT item_id,name,rarity,icon FROM item WHERE item_id IN (${marks})`, chunk)) {
        found.set(row.item_id, { item_id: row.item_id, name: row.name, rarity: row.rarity, icon: row.icon });
      }
    }
    return ids.map((id) => found.get(id) ?? { item_id: id });
  }

  areas(npcId: string): Row[] {
    return this.db.all(
      "SELECT map_id,area_id,point_count,center_x,center_y,names,polygon FROM npc_area WHERE npc_id=? ORDER BY point_count DESC",
      [String(npcId)],
    ).map((row) => ({
      map_id: row.map_id, area_id: row.area_id, point_count: row.point_count, center: [row.center_x, row.center_y],
      names: JSON.parse(row.names), polygon: JSON.parse(row.polygon),
    }));
  }
}
