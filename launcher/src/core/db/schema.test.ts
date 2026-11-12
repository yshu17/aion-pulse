import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { DB_SCHEMA, DB_SCHEMA_MAX, readSchema, schemaState } from "./schema";

describe("the database's version", () => {
  it("is the one the build writes", () => {
    const build = readFileSync(join(__dirname, "..", "..", "..", "..", "core", "pulse_db", "build.py"), "utf8");
    expect(Number(/^SCHEMA_VERSION = (\d+)/m.exec(build)![1])).toBe(DB_SCHEMA);
  });

  it("is the one the Rust side reads (db_query and the pack it downloads)", () => {
    const rust = readFileSync(join(__dirname, "..", "..", "..", "src-tauri", "src", "lib.rs"), "utf8");
    const range = /DB_SCHEMA_SUPPORTED: std::ops::RangeInclusive<i64> = (\d+)\.\.=(\d+);/.exec(rust)!;
    expect([Number(range[1]), Number(range[2])]).toEqual([DB_SCHEMA, DB_SCHEMA_MAX]);
  });

  it("fits when it is the program's or newer, and says what to do when it is older", () => {
    expect(schemaState(DB_SCHEMA)).toEqual({ found: DB_SCHEMA, fits: true, text: "" });
    expect(schemaState(DB_SCHEMA - 1).fits).toBe(false);
    expect(schemaState(DB_SCHEMA - 1).text).toContain(`нужна ${DB_SCHEMA}`);
    expect(schemaState(DB_SCHEMA_MAX + 1).fits).toBe(true);
    expect(schemaState(DB_SCHEMA_MAX + 1).text).toContain("новее");
    expect(schemaState(null).fits).toBe(false);
  });

  it("is read from the database", async () => {
    expect(await readSchema(async () => [{ user_version: DB_SCHEMA }])).toMatchObject({ found: DB_SCHEMA, fits: true });
    expect(await readSchema(async () => { throw new Error("no"); })).toMatchObject({ found: null, fits: false });
  });
});
