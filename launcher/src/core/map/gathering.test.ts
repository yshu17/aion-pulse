import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { cleanText, placesIn } from "../chat/parser";
import { Gathering, posLink, posLinks } from "./gathering";

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

  it("copies spots as the game's place links, which the chat reads back", () => {
    expect(posLink("Адамантит", "220040000", [1225, 492.9])).toBe("[pos:Адамантит;0 220040000 1225.0 492.9 0.0]");
    const node = data.inZone("220040000", null).essence.find((n) => n.name === "Адамантит")!;
    const links = posLinks(node, "220040000");
    expect(links.split("] [").length).toBe(node.points.length);
    expect(placesIn(cleanText(links))[0]).toEqual(["Адамантит", ["220040000", node.points[0][0], node.points[0][1]]]);
  });

  it("gives nothing for a zone without data or broken JSON", () => {
    expect(data.inZone("300000000", null).essence).toEqual([]);
    expect(Gathering.parse("{").inZone("220040000", null).aether).toEqual([]);
  });
});
