import { describe, expect, it } from "vitest";

import type { Stone } from "./engine";
import { enchantAdds, placeBonus, stoneAdds, stoneRows, stoneSum, stoneTabs } from "./stones";

const stone = (id: number, stat: string, grade: string, level: number, value: number): Stone => ({ id, name: `${stat}+${value}`, icon: "", grade, level, stat, value });
const all = [stone(1, "critical", "common", 10, 4), stone(2, "critical", "rare", 60, 17), stone(3, "critical", "common", 50, 12), stone(4, "critical", "rare", 20, 9),
  stone(5, "critical", "common", 50, 11), stone(6, "maxhp", "common", 10, 40), stone(7, "weird", "common", 10, 1), stone(8, "phyattack", "rare", 30, 4)];

describe("the stone picker's lists", () => {
  it("order the tabs as the game's window does and put an unknown stat last", () => {
    expect(stoneTabs(all)).toEqual(["phyattack", "critical", "maxhp", "weird"]);
  });

  it("group the white stones, then the green, the highest level first in each", () => {
    const groups = stoneRows(all, "critical");
    expect(groups.map((g) => g.grade)).toEqual(["common", "rare"]);
    expect(groups[0].rows.map((s) => s.id)).toEqual([3, 5, 1]); // level 50 (+12 before +11), then 10
    expect(groups[1].rows.map((s) => s.id)).toEqual([2, 4]);
  });

  it("keep only the strongest stone of the stat when asked, whatever its grade or level", () => {
    const best = stoneRows(all, "critical", true);
    expect(best.map((g) => g.grade)).toEqual(["rare"]);
    expect(best[0].rows.map((s) => s.id)).toEqual([2]); // «Ф. крит. +17»
    expect(stoneRows(all, "phyattack", true)[0].rows.map((s) => s.id)).toEqual([8]);
    expect(stoneRows(all, "none", true)).toEqual([]);
    expect(stoneRows([stone(1, "maxhp", "common", 10, 40), stone(2, "maxhp", "rare", 20, 40)], "maxhp", true).flatMap((g) => g.rows.map((s) => s.id))).toEqual([1, 2]); // a tie keeps both
  });

  it("add up what the chosen stones give", () => {
    expect(stoneSum([all[0], all[1], null, all[5]])).toEqual([["critical", 21], ["maxhp", 40]]);
    expect(stoneSum([])).toEqual([]);
  });
});

describe("where the extra numbers go in a card", () => {
  const blocks = [
    { kind: "grid", pairs: [["Атака", "235-437"], ["Ф. крит.", "50"], ["Сила магии", "820"]] },
    { kind: "grid", pairs: [["Физ. крит", "+52"], ["Физ. атака", "+30"], ["Макс. HP", "+264"], ["Физ. крит", "+5"]] },
    { kind: "text", text: "Усиление" },
    { kind: "stones", count: 5, bonus: 1 },
  ];

  it("puts a stone's number beside the first «+» row of its label, not beside the item's own number", () => {
    const place = placeBonus(blocks, stoneAdds([["critical", 31], ["maxhp", 40]]));
    expect([...place.deltas.entries()]).toEqual([["1:0", 31], ["1:2", 40]]);
    expect(place.extra).toEqual([]);
    expect(place.after).toBe(-1);
  });

  it("puts the enchant's attack beside the item's own attack and its defence or HP beside theirs", () => {
    const place = placeBonus(blocks, enchantAdds({ damage: 60, magicalskillboost: 300, maxhp: 56 }));
    expect([...place.deltas.entries()]).toEqual([["0:0", 60], ["0:2", 300], ["1:2", 56]]);
  });

  it("adds the enchant's and the stones' numbers of one row together, and keeps what has no row as extra rows of its group", () => {
    const place = placeBonus(blocks, [...stoneAdds([["phyattack", 4], ["magicalskillboost", 22]]), ...enchantAdds({ physicaldefend: 90, maxhp: 30 })]);
    expect([...place.deltas.entries()]).toEqual([["1:1", 4], ["1:2", 30]]);
    expect(place.extra).toEqual([{ group: "stone", label: "Сила магии", value: 22 }, { group: "enchant", label: "Физ. защита", value: 90 }]);
    expect(place.after).toBe(1);
  });

  it("falls back to the place before the stones block when the card has no «+» grid", () => {
    expect(placeBonus([{ kind: "text", text: "x" }, { kind: "stones", count: 1 }], stoneAdds([["maxhp", 5]])).after).toBe(0);
  });
});
