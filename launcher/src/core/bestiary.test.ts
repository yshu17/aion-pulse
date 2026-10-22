// Step 7 of the port: core/bestiary replays the Python golden results (tools/golden_bestiary.py) on the fixture
// database, and on the real local database when local/bestiary/ has it.
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { inflateSync } from "node:zlib";
import { describe, expect, it } from "vitest";

import {
  CATEGORY, dropsEmptyText, dropsNote, filterDrops, filterStock, KB_ITEM_URL, locationsText, overviewRows, overviewText,
  placeCounts, pointsFromText, RARITY, SORTS, stockNote,
} from "./bestiary/card";
import { aboveMaxLevel, isMainNpc, plan, stemKey, technicalName } from "./bestiary/classify";
import { factionFor, FACTIONS, raceLabel, RACES, statText } from "./bestiary/labels";
import { SearchWorker } from "./bestiary/searchWorker";
import { BestiaryStore, Db, Inflate, searchKey, unpackIds } from "./bestiary/store";

const ROOT = join(__dirname, "..", "..", "..");
const golden = (name: string) => JSON.parse(readFileSync(join(ROOT, "tests", "golden", `${name}.json`), "utf-8")).case;
const REAL = join(ROOT, "local", "bestiary", "npcs.sqlite");
const REAL_GOLDEN = join(ROOT, "local", "bestiary", "golden_real.json");

const inflate: Inflate = (data, dictionary) => new Uint8Array(inflateSync(data, dictionary ? { dictionary } : {}));

function openDb(path: string): Db {
  const db = new DatabaseSync(path, { readOnly: true });
  return {
    all: (sql, params = []) => db.prepare(sql).all(...(params as any[])) as any[],
    run: (sql, params = []) => { db.prepare(sql).run(...(params as any[])); },
    func: (name, fn) => db.function(name, { deterministic: true }, fn as any),
  };
}

/** Python's search(**kwargs) arguments as SearchOptions (the same names). */
function replay(store: BestiaryStore, want: any) {
  expect(store.version).toBe(want.version);
  expect(store.coverage()).toEqual(want.coverage);
  expect(store.races()).toEqual(want.races);
  expect(store.ranks()).toEqual(want.ranks);
  expect(store.zones()).toEqual(want.zones);
  expect([store.regions(), store.regions("210010000")]).toEqual(want.regions);
  for (const [query, rows, total] of want.search) {
    const [gotRows, gotTotal] = store.search(query);
    expect([JSON.parse(JSON.stringify(gotRows)), gotTotal], JSON.stringify(query)).toEqual([rows, total]);
  }
  for (const [id, detail] of Object.entries(want.detail)) expect(store.detail(id), id).toEqual(detail);
  for (const [id, areas] of Object.entries(want.areas)) expect(store.areas(id), id).toEqual(areas);
}

describe("bestiary store", () => {
  const g = golden("bestiary_store");
  it("answers the fixture database as in Python", () => {
    replay(new BestiaryStore(openDb(join(ROOT, "tests", "golden", "bestiary_fixture.sqlite")), inflate), g);
    for (const [hex, want] of g.unpack_ids) {
      expect([...unpackIds(Uint8Array.from(Buffer.from(hex, "hex")), inflate)].sort((a, b) => a - b)).toEqual(want);
    }
    for (const [text, want] of g.search_key) expect(searchKey(text), text).toBe(want);
  });
  it.skipIf(!existsSync(REAL) || !existsSync(REAL_GOLDEN))("answers the real local database as in Python", () => {
    replay(new BestiaryStore(openDb(REAL), inflate), JSON.parse(readFileSync(REAL_GOLDEN, "utf-8")).case);
  });
});

describe("bestiary labels, classification and card", () => {
  it("label factions, races and numbers as in Python", () => {
    const g = golden("bestiary_labels");
    expect([FACTIONS, RACES]).toEqual([g.factions, g.races]);
    for (const [a, b, want] of g.faction) expect(factionFor(a, b), `${a}|${b}`).toBe(want);
    for (const [a, b, want] of g.race) expect(raceLabel(a, b), `${a}|${b}`).toBe(want);
    for (const [v, want] of g.stat) expect(statText(v), String(v)).toBe(want);
  });
  it("classify names, levels and duplicates as in Python", () => {
    const g = golden("bestiary_classify");
    for (const [name, want] of g.technical) expect(technicalName(name), name).toBe(want);
    for (const [name, want] of g.stems) expect(stemKey(name), name).toEqual(want);
    for (const [level, category, want] of g.above) expect(aboveMaxLevel(level, category), `${level} ${category}`).toBe(want);
    for (const [badge, role, goods, want] of g.main) expect(isMainNpc(badge, role, goods)).toBe(want);
    for (const [rows, donors, service] of g.plans) {
      const [gotDonors, gotService] = plan(rows);
      expect([gotDonors, [...gotService].sort()]).toEqual([donors, service]);
    }
  });
  it("write the card as in Python", () => {
    const g = golden("bestiary_card");
    expect([CATEGORY, SORTS, RARITY, KB_ITEM_URL]).toEqual(g.consts);
    const names = { "210010000": "Фоэта", "220010000": "Исхальген", "": "—" };
    for (const [detail, rows, text, places, empty, locations, from, filters, notes] of g.cards) {
      expect(overviewRows(detail)).toEqual(rows);
      expect(overviewText(detail)).toBe(text);
      expect(placeCounts(detail, names)).toEqual(places);
      expect([dropsEmptyText(detail), locationsText(detail), pointsFromText(detail)]).toEqual([empty, locations, from]);
      for (const [q, drops, stock] of filters) expect([filterDrops(detail, q), filterStock(detail, q)], q).toEqual([drops, stock]);
      expect([dropsNote(0, detail), dropsNote(2, detail)]).toEqual(notes);
    }
    for (const [shown, total, want] of g.stock_note) expect(stockNote(shown, total)).toBe(want);
  });
});

describe("bestiary search worker", () => {
  it("collapses a burst of requests to the newest and reports errors", () => {
    const jobs: (() => void)[] = [];
    const asked: string[] = [];
    let opened = 0;
    const worker = new SearchWorker(() => {
      opened += 1;
      return { search: (o) => { asked.push(o.text ?? ""); if (o.text === "bad") throw new Error("broken"); return [[{ id: o.text }], 1]; } };
    }, (job) => jobs.push(job));
    expect(opened).toBe(0);
    for (const text of ["в", "во", "вол"]) worker.submit(text.length, { text });
    expect(jobs.length).toBe(1);
    jobs.shift()!();
    expect([opened, asked, worker.latest()]).toEqual([1, ["вол"], { seq: 3, rows: [{ id: "вол" }], total: 1, error: "" }]);
    expect(worker.latest()).toBeNull();
    worker.submit(4, { text: "bad" });
    jobs.shift()!();
    worker.submit(5, { text: "волк" });
    jobs.shift()!();
    expect(worker.latest()).toEqual({ seq: 5, rows: [{ id: "волк" }], total: 1, error: "" });
    worker.close();
    worker.submit(6, { text: "x" });
    expect(jobs.length).toBe(0);

    const broken = new SearchWorker(() => { throw new RangeError("Неизвестный формат базы бестиария: 9"); }, (job) => job());
    broken.submit(1, {});
    broken.submit(2, {});
    expect(broken.latest()).toEqual({ seq: 2, rows: [], total: 0, error: "Неизвестный формат базы бестиария: 9" });
  });
});
