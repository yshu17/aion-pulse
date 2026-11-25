import { describe, expect, it } from "vitest";

import type { GearItem } from "./engine";
import { applySet, planSet } from "./wearSet";

const piece = (id: number, slot: string, grp: string, over: Partial<GearItem> = {}) =>
  ({ id, slot, grp, classes: ["fighter"], stones: 0, stonesBonus: 0, level: 50, ...over } as GearItem);

const TORSO = piece(1, "torso", "lt_torso");
const GLOVE = piece(2, "glove", "lt_glove");
const SHOES = piece(3, "shoes", "lt_shoes", { stones: 2 });
const RING_A = piece(4, "ring", "ring");
const RING_B = piece(5, "ring", "ring");
const MACE = piece(6, "main_or_sub", "mace");
const SHIELD = piece(7, "sub", "shield");
const SPEAR = piece(8, "main", "polearm");
const OTHER_GLOVE = piece(9, "glove", "pl_glove");
const MAGE_HAT = piece(10, "head", "rb_head", { classes: ["wizard"] });

const known = (...list: GearItem[]) => new Map(list.map((i) => [i.id, i]));
const worn = (id: number, enchant = 0, stones: (number | null)[] = []) => ({ id, enchant, stones });

describe("planning to wear a set", () => {
  it("puts the missing pieces into their free slots and leaves the worn ones as they are", () => {
    const slots = { torso: worn(1, 10, [7]) };
    const plan = planSet(slots, [TORSO, GLOVE, SHOES], known(TORSO), "fighter");
    expect(plan.puts.map((p) => [p.slot, p.item.id])).toEqual([["glove", 2], ["shoes", 3]]);
    expect(plan.removed).toEqual([]);
    const out = applySet(slots, plan);
    expect(out.torso).toEqual(worn(1, 10, [7])); // its enchant and stones stay
    expect(out.shoes).toEqual(worn(3, 0, [null, null]));
  });

  it("says what a busy slot would lose, and can wear into the free slots only", () => {
    const slots = { glove: worn(9, 10) };
    const plan = planSet(slots, [GLOVE, SHOES], known(OTHER_GLOVE), "fighter");
    expect(plan.removed).toEqual([{ slot: "glove", id: 9 }]);
    expect(applySet(slots, plan).glove?.id).toBe(2);
    const free = applySet(slots, plan, true);
    expect(free.glove).toEqual(worn(9, 10));
    expect(free.shoes?.id).toBe(3);
  });

  it("gives two rings of a set two different slots, a free one first", () => {
    const plan = planSet({ ring1: worn(99) }, [RING_A, RING_B], known(), "fighter");
    expect(plan.puts.map((p) => [p.slot, p.item.id])).toEqual([["ring2", 4], ["ring1", 5]]);
    expect(plan.removed).toEqual([{ slot: "ring1", id: 99 }]);
  });

  it("empties the off hand for a two-hander, and the two-hander for a shield", () => {
    const spear = planSet({ sub: worn(7) }, [SPEAR], known(SHIELD), "fighter");
    expect(spear.removed).toEqual([{ slot: "sub", id: 7 }]);
    expect(applySet({ sub: worn(7) }, spear)).toEqual({ main: worn(8) });
    const shield = planSet({ main: worn(8) }, [SHIELD], known(SPEAR), "fighter");
    expect(shield.removed).toEqual([{ slot: "main", id: 8 }]);
    expect(applySet({ main: worn(8) }, shield)).toEqual({ sub: worn(7) });
    expect(applySet({ main: worn(8) }, shield, true)).toEqual({ main: worn(8) }); // «only free» keeps the two-hander
  });

  it("puts a one-hand weapon in the main hand and a shield beside it", () => {
    const plan = planSet({}, [SHIELD, MACE], known(), "fighter");
    expect(plan.puts.map((p) => [p.slot, p.item.id]).sort()).toEqual([["main", 6], ["sub", 7]]);
  });

  it("leaves out what the class cannot wear and has nothing to do when the set is already on", () => {
    expect(planSet({}, [MAGE_HAT, GLOVE], known(), "fighter").cannot.map((i) => i.id)).toEqual([10]);
    expect(planSet({ glove: worn(2) }, [GLOVE], known(GLOVE), "fighter").puts).toEqual([]);
  });
});
