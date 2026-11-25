import { describe, expect, it } from "vitest";

import { activeBuffs, buffKey, readBuffs, toggleBuff, type BuffTable } from "./buffs";

const step = (name: string) => [{ level: 1, name, icon: null, effects: [{ type: "statup", name }] }];
// «Благословение жизни» has one id (951) at the cleric and at the chanter
const TABLE: BuffTable = {
  cleric: [{ id: 951, share: true, chain: step("Жизнь целителя") }, { id: 1105, share: true, chain: step("Покровительство огня") }],
  chanter: [{ id: 951, share: true, chain: step("Жизнь чародея") }, { id: 1207, share: true, chain: step("Победа") }],
  fighter: [{ id: 700, share: false, chain: step("Ярость") }],
};
const names = (keys: (string | number)[], cls = "fighter") => activeBuffs(readBuffs(keys, cls, TABLE), cls, 55, TABLE).map((s) => s.name);

describe("the buffs of the gear calculator", () => {
  it("tells apart two classes' buffs with one id: one click is one buff, counted once", () => {
    const on = toggleBuff([], buffKey("cleric", 951));
    expect(on).toEqual(["cleric:951"]);
    expect(names(on)).toEqual(["Жизнь целителя"]);
  });

  it("keeps the healer's and the chanter's version of one buff from working together: the new one replaces the other", () => {
    const on = toggleBuff(["cleric:951", "cleric:1105"], "chanter:951");
    expect(on).toEqual(["cleric:1105", "chanter:951"]);
    expect(names(on)).toEqual(["Покровительство огня", "Жизнь чародея"]); // the table's order: the cleric first
    expect(toggleBuff(on, "chanter:951")).toEqual(["cleric:1105"]);
  });

  it("reads the numbers of builds saved before: the class's own skill first, else one owner, never two", () => {
    expect(readBuffs([951], "chanter", TABLE)).toEqual(["chanter:951"]);
    expect(readBuffs([951, 700, 12345], "fighter", TABLE)).toEqual(["cleric:951", "fighter:700"]);
    expect(readBuffs(["cleric:951", "chanter:951"], "fighter", TABLE)).toEqual(["chanter:951"]);
  });

  it("leaves out another class's own skill that it does not share", () => {
    expect(names(["fighter:700"], "cleric")).toEqual([]);
    expect(names(["fighter:700"], "fighter")).toEqual(["Ярость"]);
  });
});
