// The TypeScript core gives the same results as the Python core (tests/golden/*.json, made by tools/golden_gen.py).
import { createHash } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { parseLinkNames, parseNames, parseWatchItems } from "./items/catalog";
import { readConfig, serializeConfig, defaultConfig } from "./settings/config";
import { parseZones } from "./map/zones";

const ROOT = join(__dirname, "..", "..", "..");
const DATA = join(ROOT, "data");
const golden = (name: string) => JSON.parse(readFileSync(join(ROOT, "tests", "golden", `${name}.json`), "utf-8")).case;
const text = (path: string) => (existsSync(path) ? readFileSync(path, "utf-8") : null);

/** json.dumps(value, ensure_ascii=False, sort_keys=True) of Python, for strings, integers, lists and objects. */
function pyDumps(value: unknown): string {
  if (Array.isArray(value)) return "[" + value.map(pyDumps).join(", ") + "]";
  if (value && typeof value === "object") {
    return "{" + Object.keys(value).sort().map((k) => `${JSON.stringify(k)}: ${pyDumps((value as any)[k])}`).join(", ") + "}";
  }
  return JSON.stringify(value);
}
const digest = (value: unknown) => createHash("sha256").update(pyDumps(value), "utf-8").digest("hex");
const byKey = (record: Record<string, string>) => Object.entries(record).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));

describe("settings", () => {
  const g = golden("settings");
  it("defaults match", () => {
    expect(defaultConfig()).toEqual(g.defaults);
  });
  it("a value of the wrong type takes its default and is named", () => {
    const input = { keywords: ["wts", 5], cooldown_sec: 30, alert_mode: "nag", react_sec: "30", notify_corner: "top",
      unknown_key: 1 };
    const result = readConfig(JSON.stringify(input));
    expect(result.config).toEqual(g.mixed_types.config);
    expect(result.notice).toBe(g.mixed_types.notice);
    expect(result.action).toBeNull();
  });
  it("a broken file gives the defaults and a backup", () => {
    const result = readConfig("не json", "config.json.broken-20261022-120000");
    expect(result.config).toEqual(g.broken_file.config);
    expect(result.notice.slice(0, 20)).toBe(g.broken_file.notice_starts);
    expect(result.action).toBe("backup_and_write");
    expect(readConfig(null).action).toBe("write_defaults");
  });
  it("writing keeps the values and the field order", () => {
    const config = { ...defaultConfig(), keywords: ["хил"], watch_items: ["1"] };
    const dir = mkdtempSync(join(tmpdir(), "pulse-config-"));
    writeFileSync(join(dir, "config.json"), serializeConfig(config), "utf-8");
    const saved = JSON.parse(readFileSync(join(dir, "config.json"), "utf-8"));
    expect({ keywords: saved.keywords, watch_items: saved.watch_items }).toEqual(g.saved_keys);
    expect(Object.keys(saved)).toEqual(Object.keys(g.defaults).length ? Object.keys(defaultConfig()) : []);
  });
});

describe("loaders on the real data", () => {
  const g = golden("loaders");
  it("item names", () => {
    const names = parseNames(text(join(DATA, "item_names.tsv")));
    const ids = Object.keys(names).sort();
    expect(ids.length).toBe(g.item_names.count);
    expect([ids[0], names[ids[0]]]).toEqual(g.item_names.sample);
    expect(digest(byKey(names))).toBe(g.item_names.digest);
  });
  it("map and quest names", () => {
    const [maps, quests] = parseLinkNames(text(join(DATA, "map_names.tsv")), text(join(DATA, "quest_names.tsv")));
    expect([Object.keys(maps).length, Object.keys(quests).length]).toEqual([g.link_names.maps, g.link_names.quests]);
    expect(digest([byKey(maps), byKey(quests)])).toBe(g.link_names.digest);
  });
  it("watch items", () => {
    const items = parseWatchItems(text(join(DATA, "watch_items.csv")));
    expect(items.length).toBe(g.watch_items.count);
    expect(digest(items.map((w) => [w.id, w.name, w.level, w.category, w.grade, w.kind]))).toBe(g.watch_items.digest);
  });
  it("zones", () => {
    const maps = join(DATA, "maps");
    const [mapNames] = parseLinkNames(text(join(DATA, "map_names.tsv")), null);
    const zones = parseZones(text(join(maps, "maps.json")), text(join(maps, "labels.tsv")), mapNames,
      (file) => existsSync(join(maps, file)));
    const list = Object.values(zones).sort((a, b) => (a.map_id < b.map_id ? -1 : 1)).map((z) => ({
      map_id: z.map_id, name: z.name, file: z.file.split("/").pop(), size: z.size, kx: z.kx, ky: z.ky, side: z.side,
      labels: z.labels.length, layers: z.layers.map((layer) => layer[0]),
    }));
    expect(list.length).toBe(g.zones.count);
    expect(list).toEqual(g.zones.list);
  });
});
