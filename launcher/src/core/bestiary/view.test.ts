import { describe, expect, it } from "vitest";

import { iconPath, LEVELS, levelRange, mainPlace, RANK_CHIPS, rarityClass, roleLabel, rowSubtitle } from "./view";

describe("bestiary screen helpers", () => {
  it("turns a level choice into the store's bounds, «Любой» into none", () => {
    expect(LEVELS[0]).toBe("Любой");
    expect(levelRange("Любой")).toEqual({ min_level: null, max_level: null });
    expect(levelRange("11–20")).toEqual({ min_level: 11, max_level: 20 });
    expect(levelRange("56+")).toEqual({ min_level: 56, max_level: null });
    expect(levelRange("что-то")).toEqual({ min_level: null, max_level: null });
  });

  it("offers the rank classes of the database as chips, «Все» first", () => {
    expect(RANK_CHIPS[0]).toEqual(["Все", ""]);
    expect(RANK_CHIPS.map(([, rank]) => rank)).toEqual(["", "Обычный", "Элитный", "Героический", "Легендарный"]);
  });

  it("writes a row's line as level, kind and rank, leaving out what is missing", () => {
    expect(rowSubtitle({ level: 55, kind: "Торговец", rank: "Обычный" })).toBe("Ур. 55 · Торговец · Обычный");
    expect(rowSubtitle({ level: "", kind: "Монстр", rank: "" })).toBe("Монстр");
    expect(rowSubtitle({})).toBe("");
  });

  it("finds the zone with the most points and the first point there", () => {
    const detail = { points: [
      { map_id: "110010000", gx: 1, gy: 2 }, { map_id: "220070000", gx: 10, gy: 20 }, { map_id: "220070000", gx: 11, gy: 21 },
    ] };
    expect(mainPlace(detail)).toEqual({ map_id: "220070000", count: 2, gx: 10, gy: 20 });
    expect(mainPlace({ points: [] })).toBeNull();
    expect(mainPlace({})).toBeNull();
  });

  it("finds an icon in the bestiary's icon folders: a bare drop icon is an item picture", () => {
    expect(iconPath("npc/icon_emblem_merchant.jpg")).toBe("npc/icon_emblem_merchant.jpg");
    expect(iconPath("client/icon_item_battery01.png")).toBe("client/icon_item_battery01.png");
    expect(iconPath("icon_item_x.jpg")).toBe("items/icon_item_x.jpg");
    expect(iconPath("")).toBeNull();
    expect(iconPath(undefined)).toBeNull();
  });

  it("colours an item by its rarity, the junk one too", () => {
    expect(rarityClass("epic")).toBe("g-epic");
    expect(rarityClass("junk")).toBe("g-junk");
    expect(rarityClass("")).toBe("g-common");
  });

  it("names the service of an NPC's role in Russian", () => {
    expect(roleLabel("merchant")).toBe("Торговец");
    expect(roleLabel("teleport")).toBe("Телепорт");
    expect(roleLabel("")).toBe("");
    expect(roleLabel("unknown_role")).toBe("");
  });
});
