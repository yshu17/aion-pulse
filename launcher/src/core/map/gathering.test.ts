import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { cleanText, placesIn } from "../chat/parser";
import { Gathering, posLink } from "./gathering";

const ROOT = join(__dirname, "..", "..", "..", "..");
const data = Gathering.parse(readFileSync(join(ROOT, "data", "maps", "gathering.json"), "utf-8"));

describe("gathering nodes", () => {
  it("splits a zone's nodes into energy (essence) and aether gathering, by level", () => {
    const { essence, aether } = data.inZone("220040000", null); // Белуслан
    expect(essence.length).toBeGreaterThan(20);
    expect(aether.length).toBe(9);
    expect(aether.every((n) => n.kind === "aether")).toBe(true);
    const levels = essence.map((n) => n.level);
    expect(levels).toEqual([...levels].sort((a, b) => a - b));
    const adamantium = essence.find((n) => n.name === "Адамантит")!;
    expect(adamantium.level).toBe(200);
    expect(adamantium.points.length).toBe(183); // each spot once: the site has 278, some twice or 0.1 m apart
  });

  it("keeps the Abyss layers apart", () => {
    const lower = data.inZone("400010000", 1);
    const upper = data.inZone("400010000", 3);
    expect(lower.essence.length + lower.aether.length).toBe(12);
    expect(upper.essence.length + upper.aether.length).toBe(7);
    expect(data.inZone("400010000", 2).essence.length).toBe(0);
  });

  it("has the client's zones and dungeons the site lacks (Inggison, Gelkmaros, Araka)", () => {
    for (const id of ["210050000", "220070000", "600020000"]) expect(data.inZone(id, null).essence.length).toBeGreaterThan(15);
    const araka = data.inZone("300250000", null).essence;
    expect(araka.map((n) => n.name)).toContain("Сломанный древесный ствол / Причудливый ключ");
  });

  it("writes a spot as the game's own place link, which the chat reads back", () => {
    expect(posLink("Адамантит", "220040000", [1225, 492.9])).toBe("[pos:Адамантит;220040000 1225.0 492.9 0.0 0]");
    const node = data.inZone("220040000", null).essence.find((n) => n.name === "Адамантит")!;
    const link = posLink(node.name, "220040000", node.points[0]);
    expect(placesIn(cleanText(link))[0]).toEqual(["Адамантит", ["220040000", node.points[0][0], node.points[0][1]]]);
  });

  it("finds a resource by name in every zone it grows in, grouped, the closest level first", () => {
    const hits = data.find("орихалк", 8);
    expect(hits.length).toBeGreaterThan(0);
    const hit = hits[0];
    expect(hit.name).toBe("Орихалк");
    expect(hit.level).toBe(300);
    expect(hit.places.map((p) => p.map_id)).toContain("220050000"); // Брустхонин
    expect(hit.places.every((p) => p.node.name === "Орихалк" && p.node.points.length > 0)).toBe(true);
    // the words may come in any order and «ё» is «е»; the English name of the site finds too
    expect(data.find("эфира сгусток", 8).some((h) => h.name === "Сгусток эфира")).toBe(true);
    expect(data.find("mithril", 8).some((h) => h.name === "Мифрил")).toBe(true);
    expect(data.find("о", 8)).toEqual([]); // one letter is not a search
    expect(data.find("нетакогоресурса", 8)).toEqual([]);
    expect(data.find("с", 3)).toEqual([]);
    expect(data.find("сгусток", 2).length).toBe(2); // the limit
  });

  it("puts a name that starts with the query before one that only contains it", () => {
    const names = data.find("рубин", 8).map((h) => h.name);
    expect(names.indexOf("Рубин")).toBeGreaterThanOrEqual(0);
    expect(names.indexOf("Рубин")).toBeLessThan(names.indexOf("Огромный рубин"));
  });

  it("keeps the Abyss layers of a found resource apart", () => {
    const hit = data.find("титан", 8).find((h) => h.places.some((p) => p.map_id === "400010000"))!;
    expect(hit.places.filter((p) => p.map_id === "400010000").every((p) => p.node.layer !== null)).toBe(true);
  });

  it("gives nothing for a zone without data or broken JSON", () => {
    expect(data.inZone("300000000", null).essence).toEqual([]);
    expect(Gathering.parse("{").inZone("220040000", null).aether).toEqual([]);
  });
});
