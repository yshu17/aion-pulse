import { readFileSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";

import { decodeJson, Drop, GameData } from "./gameData/gameData";

const DATA = join(__dirname, "../../../data/game"); // built by tools/build_game_data.py, kept in git (but drops.sqlite)

const fromFolder = (folder: string) => async (file: string) => {
  try { return new Uint8Array(readFileSync(join(folder, file))); } catch { return null; }
};

const fromMap = (files: Record<string, unknown>) => async (file: string) => {
  if (!(file in files)) return null;
  const text = JSON.stringify(files[file]);
  return new Uint8Array(file.endsWith(".gz") ? gzipSync(text) : Buffer.from(text));
};

describe("game data reader", () => {
  it("reads the real data folder: manifest, items by id, a table", async () => {
    const data = new GameData(fromFolder(DATA));
    const manifest = await data.manifest();
    expect(manifest?.schema).toBe(1);
    expect(manifest?.sections.items.records).toBe(62490);
    const items = await data.byId("items");
    expect(items.size).toBe(62490);
    expect(items.get("100000001")?.name).toBe("Меч Циркулоса");
    const vendors = await data.table("vendors");
    expect(vendors.columns).toEqual(["npc", "item", "price", "currency", "limit", "kind"]);
    expect(vendors.rows.length).toBe(41516);
    const { skills, learns } = await data.skills();
    expect(skills.length).toBe(7560);
    expect(learns.length).toBeGreaterThan(0);
    expect((await data.byId("classes")).get("ASSASSIN.PC_DARK")?.base_stats).toBeNull(); // not found in the client yet
  });

  it("loads a section once, however many screens ask for it", async () => {
    let reads = 0;
    const files = { "items.json.gz": { schema: 1, section: "items", records: [{ id: "1", name: "Меч" }] } };
    const read = fromMap(files);
    const data = new GameData(async (file) => { reads += 1; return read(file); });
    const [a, b] = await Promise.all([data.records("items"), data.records("items")]);
    expect(a).toBe(b);
    await data.byId("items");
    expect(reads).toBe(1);
  });

  it("reads a missing, broken or foreign file as empty data", async () => {
    const data = new GameData(async (file) => {
      if (file === "items.json.gz") return new Uint8Array([1, 2, 3]); // not gzip
      if (file === "npcs.json.gz") return new Uint8Array(gzipSync(JSON.stringify({ schema: 99, records: [{ id: "1" }] }))); // another schema
      return null;
    });
    expect(await data.manifest()).toBeNull();
    expect(await data.records("items")).toEqual([]);
    expect(await data.records("npcs")).toEqual([]);
    expect(await data.table("vendors")).toEqual({ columns: [], rows: [] });
    expect(await data.skills()).toEqual({ skills: [], learns: [] });
  });

  it("asks the drops from the program and keeps the browser without them", async () => {
    const drop: Drop = { npc_id: 210065, item_id: 100000001, chance_min: null, chance_max: null, count_min: null, count_max: null };
    const asked: string[] = [];
    const data = new GameData(fromMap({}), { ofNpc: async (id) => { asked.push(`npc ${id}`); return [drop]; }, droppers: async (id) => { asked.push(`item ${id}`); return [drop]; } });
    expect(await data.dropsOfNpc("210065")).toEqual([drop]);
    expect(await data.droppersOf("100000001")).toEqual([drop]);
    expect(await data.dropsOfNpc("abc")).toEqual([]); // not an id: not asked
    expect(asked).toEqual(["npc 210065", "item 100000001"]);
    expect(await new GameData(fromMap({})).dropsOfNpc("210065")).toEqual([]);
    const failing = new GameData(fromMap({}), { ofNpc: async () => { throw new Error("no file"); }, droppers: async () => [] });
    expect(await failing.dropsOfNpc("1")).toEqual([]);
  });

  it("decodes plain and gzipped JSON, and nothing else", async () => {
    expect(await decodeJson(new Uint8Array(gzipSync('{"a":1}')), true)).toEqual({ a: 1 });
    expect(await decodeJson(new TextEncoder().encode("[1,2]"), false)).toEqual([1, 2]);
    expect(await decodeJson(new TextEncoder().encode("not json"), false)).toBeNull();
    expect(await decodeJson(new TextEncoder().encode('{"a":2}'), true)).toEqual({ a: 2 }); // a server unpacked the «.gz» already
    expect(await decodeJson(new Uint8Array([0x1f, 0x8b, 1, 2]), true)).toBeNull(); // a broken gzip
  });
});
