import { describe, expect, it } from "vitest";

import { messageSegments } from "../chat/segments";
import { cardGrade, headBlocks, segmentItemIds, statValue } from "./card";

describe("item card", () => {
  const names = { "1": "Камень Рудры", "2": "Камень Рудры", "3": "Свиток скорости" };
  const known = (id: string) => id in names;

  it("gives each item link its own id: two items of one name stay apart", () => {
    const spec = { "Камень Рудры": "2", "Свиток скорости": "3" }; // a name stands for its last id, as in Pulse
    const segments = messageSegments("wts [Камень Рудры] и [Камень Рудры], [Свиток скорости]", [], spec);
    expect(segmentItemIds(segments, ["2", "1", "3"], names, known).filter(Boolean)).toEqual(["2", "1", "3"]);
  });

  it("falls back to the id of the name when the link's own id is unknown or missing", () => {
    const segments = messageSegments("[Свиток скорости] дёшево", [], { "Свиток скорости": "3" });
    expect(segmentItemIds(segments, ["999"], { ...names, "999": "Свиток скорости" }, known).filter(Boolean)).toEqual(["3"]);
    expect(segmentItemIds(segments, [], names, known).filter(Boolean)).toEqual(["3"]);
  });

  it("keeps plain text and places without an id", () => {
    const segments = messageSegments("ищу группу", [], {});
    expect(segmentItemIds(segments, ["3"], names, known)).toEqual([null]);
  });

  it("writes stats as the game: one minus, tenths of a percent for aggression and PvP", () => {
    expect(statValue("Агрессия", "+50%")).toBe("+5.0%");
    expect(statValue("Агрессия", "+-16%")).toBe("-1.6%");
    expect(statValue("Защита в ПвП", "+52")).toBe("+5.2%");
    expect(statValue("Защита в ПвП", "+-40")).toBe("-4.0%");
    expect(statValue("Урон в ПвП", "+100")).toBe("+10.0%");
    expect(statValue("Сила исцеления", "+-7")).toBe("-7");
    expect(statValue("Скорость атаки", "+19%")).toBe("+19%");
    expect(statValue("Физ. защита", "+74")).toBe("+74");
  });

  it("writes every grade in lower case (some descriptions have «Unique»)", () => {
    expect(cardGrade("Unique")).toBe("unique");
    expect(cardGrade(undefined, "Legend")).toBe("legend");
    expect(cardGrade(undefined)).toBe("common");
  });

  it("puts the leading type, properties and warning beside the picture, as Pulse does", () => {
    const blocks = [{ kind: "pairs" }, { kind: "props" }, { kind: "warning" }, { kind: "hr" }, { kind: "props" }];
    const [head, rest] = headBlocks(blocks);
    expect(head.map((b) => b.kind)).toEqual(["pairs", "props", "warning"]);
    expect(rest.map((b) => b.kind)).toEqual(["hr", "props"]);
  });
});
