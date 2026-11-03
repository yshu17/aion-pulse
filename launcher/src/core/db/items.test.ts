import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { deflateSync } from "node:zlib";
import { describe, expect, it } from "vitest";

import { itemCatalog, itemSpecs } from "./items";
import type { All } from "./npcPoints";

const SCHEMA = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "schema.sql"), "utf8");
const DICT = Buffer.from('{"name":"","grade":"unique","blocks":[{"kind":"hr"}]}');
const spec = (value: object) => deflateSync(Buffer.from(JSON.stringify(value)), { dictionary: DICT }); // as build.py pack_spec

/** A small pulse.db in memory with the real schema: two items with a card (in the catalog's order), one name only. */
function sample(): All {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  const add = db.prepare("INSERT INTO item (id, name, name_key, level, category, grade, kind, icon, catalog_ord, spec) VALUES (?,?,?,?,?,?,?,?,?,?)");
  add.run(901, "Меч, древний", "меч, древний", 55, "Оружие", "unique", "Меч", "icon_item_sword", 1, spec({ name: "Меч, древний", blocks: [{ kind: "hr" }] }));
  add.run(902, "Зелье жизни", "зелье жизни", null, "Припасы", "common", null, null, 0, null);
  add.run(907, "Только в ссылках", "только в ссылках", null, null, null, null, null, null, null);
  db.prepare("INSERT INTO meta (key, value) VALUES ('spec_dict', ?)").run(DICT);
  return async (sql, params = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
}

describe("the items from pulse.db", () => {
  it("gives the names of chat links and the catalog of cards in its order, as watch_items.csv did", async () => {
    const { names, catalog } = await itemCatalog(sample());
    expect(names).toEqual({ "901": "Меч, древний", "902": "Зелье жизни", "907": "Только в ссылках" });
    expect(catalog.map((item) => item.id)).toEqual(["902", "901"]);
    expect(catalog[1]).toEqual({ id: "901", name: "Меч, древний", level: 55, category: "Оружие", grade: "unique", icon: "icon_item_sword", kind: "Меч" });
    expect(catalog[0]).toMatchObject({ level: NaN, icon: "", kind: "" }); // no level: as parseInt of an empty field
  });

  it("gives a card's description, unpacked with the database's dictionary; none for an item without one", async () => {
    const specs = itemSpecs(sample());
    expect(await specs("901")).toEqual({ name: "Меч, древний", blocks: [{ kind: "hr" }] });
    expect(await specs("902")).toBeNull();
    expect(await specs("nobody")).toBeNull();
  });
});
