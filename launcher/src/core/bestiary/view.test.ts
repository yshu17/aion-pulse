import { describe, expect, it } from "vitest";

import { hpFrame, iconPath, rankTier, statGroups, LEVELS, levelRange, mainPlace, placeAt, RANK_CHIPS, rarityClass, roleLabel, rowSubtitle } from "./view";

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
  it("takes the HP artwork of the card from the sprite by the NPC's rank, as Pulse does", () => {
    expect(hpFrame({ hp_bar: 3 })).toEqual({ rank: 3, frame: [5, 205, 333, 296], iconTop: 25, iconLeft: 27, levelTop: 42, levelLeft: 14 });
    expect(hpFrame({ rank: "Элитный" })).toEqual({ rank: 2, frame: [26, 98, 310, 188], iconTop: 25, iconLeft: 24, levelTop: 44, levelLeft: 14 });
    expect(hpFrame({ hp_bar: 1 })).toEqual({ rank: 1, frame: [25, 0, 297, 79], iconTop: 22, iconLeft: 30, levelTop: 41, levelLeft: 19 });
    expect(hpFrame({ hp_bar: 4 })?.levelTop).toBe(46);
    expect(hpFrame({ rank: "Легендарный" })?.rank).toBe(4);
    expect(hpFrame({ hp_bar: 9 })?.rank).toBe(1); // an unknown bar falls back to the plain one
    expect(hpFrame({ rank: "" })).toBeNull();
    expect(hpFrame({})).toBeNull();
  });

  it("finds the first point of a chosen zone, null when the NPC has none there", () => {
    const detail = { points: [{ map_id: "1", gx: 5, gy: 6 }, { map_id: "2", gx: 7, gy: 8 }, { map_id: "2", gx: 9, gy: 10 }] };
    expect(placeAt(detail, "2")).toEqual({ map_id: "2", count: 2, gx: 7, gy: 8 });
    expect(placeAt(detail, "3")).toBeNull();
  });
  it("splits the card's numbers into the four key tiles and the rest of the facts (big numbers grouped as in Pulse)", () => {
    const detail = { level: 49, rank: "Обычный", faction: "Другие", race: "Зверь",
      stats: { "Макс. ХП": "11578", "Опыт": "34623", "DP": "50", "Ранг Бездны": "Солдат, ранг 9", "Точек появления": "96 / 1 локаций" } };
    const { key, rest } = statGroups(detail);
    expect(key).toEqual([["Макс. ХП", "11 578"], ["DP", "50"], ["Опыт", "34 623"], ["Ранг Бездны", "Солдат, ранг 9"]]);
    expect(rest).toEqual([["Точек появления", "96 / 1 локаций"], ["Принадлежность", "Другие"], ["Вид", "Зверь"]]); // level and rank are in the header
    expect(statGroups({ level: 5, rank: "Обычный" }).key).toEqual([]);
  });

  it("gives a rank its tier 1…4 for the colour, 0 when unknown", () => {
    expect(rankTier("Обычный")).toBe(1);
    expect(rankTier("Легендарный")).toBe(4);
    expect(rankTier("")).toBe(0);
    expect(rankTier(undefined)).toBe(0);
  });
});
