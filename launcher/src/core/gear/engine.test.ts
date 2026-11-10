import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { calcStats, canEnchant, display, enchantBonus, passiveSkills, shown, titleLines, type Equipped, type GearItem } from "./engine";

const DATA = join(__dirname, "..", "..", "..", "..", "data", "gear", "eu20");
const classStats = JSON.parse(readFileSync(join(DATA, "class_stats.json"), "utf8")).classes;
const passives = JSON.parse(readFileSync(join(DATA, "passive_skills.json"), "utf8"));

const naked = (cls: string, level = 55) => calcStats({ cls, level, base: classStats[cls][level - 1], slots: {}, sets: [], skills: passiveSkills(cls, level, passives) });
const value = (stats: ReturnType<typeof naked>, name: string) => display(name, stats.get(name));

describe("the gear calculator's arithmetic, against aiongear.fun eu20", () => {
  it("gives a naked gladiator of level 55 the site's numbers", () => {
    const s = naked("fighter");
    // the site, 09.11.2026: https://aiongear.fun/eng/eu20/gladiator with nothing worn
    expect({
      hp: value(s, "maxhp"), mp: value(s, "maxmp"), atkSpeed: value(s, "attackdelay"), cast: value(s, "boostcastingtime"),
      speed: value(s, "speed"), fly: value(s, "flyspeed"), flyTime: value(s, "maxfp"), enmity: value(s, "boosthate"),
      attack: value(s, "r_damage"), accuracy: value(s, "r_hitaccuracy"), crit: value(s, "r_critical"), magicAcc: value(s, "magicalhitaccuracy"),
      critSpell: value(s, "magicalcritical"), power: value(s, "str"), health: value(s, "vit"), block: value(s, "block"), parry: value(s, "parry"),
      evasion: value(s, "dodge"), strikeResist: value(s, "physicalcriticalreducerate"),
    }).toEqual({
      hp: 7318, mp: 3965, atkSpeed: 1.5, cast: 1, speed: 6, fly: 9, flyTime: 60, enmity: 2, attack: 55, accuracy: 750, crit: 2,
      magicAcc: 783, critSpell: 50, power: 115, health: 115, block: 844, parry: 824, evasion: 744, strikeResist: 30,
    });
  });

  it("adds the enchant per level: +2 attack a level for a sword, the shield's damage reduction then block", () => {
    expect(enchantBonus("sword", 15)).toEqual({ damage: 30 });
    expect(enchantBonus("shield", 12)).toEqual({ damagereduce: 20, block: 60 });
    expect(enchantBonus("pl_torso", 3)).toEqual({ physicaldefend: 18, maxhp: 24, physicalcriticalreducerate: 12 });
    expect(enchantBonus("ring", 5)).toEqual({});
  });

  it("counts a two-handed weapon's attack from power, its bonuses and the armour's share of defence", () => {
    const glaive: GearItem = { id: 1, name: "Glaive", icon: "", grade: "epic", level: 55, slot: "main", grp: "polearm", classes: ["fighter"],
      basic: { mindamage: 285, maxdamage: 531, attackdelay: 2800, hitaccuracy: 0, critical: 50, attackrange: 2500 },
      bonus: [["phyattack", 38, false], ["maxhp", 347, false], ["attackdelay", 19, true]], stones: 6, stonesBonus: 1, enchant: true, setId: null };
    const torso: GearItem = { ...glaive, id: 2, slot: "torso", grp: "pl_torso", basic: { physicaldefend: 400 }, bonus: [["maxhp", 100, false]] };
    const slots: Record<string, Equipped> = { main: { item: glaive, enchant: 0, stones: [] }, torso: { item: torso, enchant: 0, stones: [] } };
    const s = calcStats({ cls: "fighter", level: 55, base: classStats.fighter[54], slots, sets: [], skills: passiveSkills("fighter", 55, passives) });
    expect(value(s, "attackrange")).toBe(2.5);
    expect(shown("attackdelay", s.get("attackdelay"))).toBeCloseTo(2.8 - 2.8 * 0.19, 5); // 19 % faster
    expect(s.get("physicaldefend")!.basic).toBe(400);
    expect(s.get("physicaldefend")!.bonus).toBe(20); // 5 % of the armour's defence
    expect(value(s, "maxhp") - value(naked("fighter"), "maxhp")).toBe(447);
  });

  it("gives a gladiator with the site's «Tac Officer's Glaive» (our «Священное копье верховного магистра арены») the site's numbers", () => {
    const glaive: GearItem = { id: 101300822, name: "Священное копье верховного магистра арены", icon: "", grade: "epic", level: 55, slot: "main",
      grp: "polearm", classes: ["fighter"], stones: 5, stonesBonus: 0, enchant: true, setId: null,
      basic: { mindamage: 285, maxdamage: 531, attackdelay: 2800, hitaccuracy: 926, critical: 50, magicalaccuracy: 331, parry: 1054, hitcount: 4, attackrange: 2500 },
      bonus: [["maxhp", 347, false], ["hitaccuracy", 15, false], ["maxmp", 346, false], ["phyattack", 6, false], ["attackdelay", 19, true],
        ["critical", 17, false], ["hitaccuracy", 143, false], ["parry", 14, false], ["phyattack", 32, false]] };
    const s = calcStats({ cls: "fighter", level: 55, base: classStats.fighter[54], slots: { main: { item: glaive, enchant: 0, stones: [] } }, sets: [],
      skills: passiveSkills("fighter", 55, passives) });
    // the site, 09.11.2026, with only that weapon: HP 7 665, MP 4 311, range 2.5, attack speed 2.268 (+19 %), [R] attack 603
    expect({ hp: value(s, "maxhp"), mp: value(s, "maxmp"), range: value(s, "attackrange"), atkSpeed: value(s, "attackdelay"), attack: value(s, "r_damage") })
      .toEqual({ hp: 7665, mp: 4311, range: 2.5, atkSpeed: 2.268, attack: 603 });
  });

  it("lets only weapons, shields and armour take an enchant; a title and a scroll add their bonus", () => {
    const base = { id: 1, name: "", icon: "", grade: "epic", level: 55, slot: "head", classes: [], basic: {}, bonus: [], stones: 0, stonesBonus: 0, enchant: true, setId: null };
    expect(canEnchant({ ...base, grp: "head" } as GearItem)).toBe(false);
    expect(canEnchant({ ...base, grp: "ring" } as GearItem)).toBe(false);
    expect(canEnchant({ ...base, grp: "polearm" } as GearItem)).toBe(true);
    expect(canEnchant({ ...base, grp: "pl_torso", enchant: false } as GearItem)).toBe(false);
    expect(titleLines(["maxHp 20", "speed 5%"])).toEqual([["maxhp", 20, false], ["speed", 5, true]]);
    const plain = naked("fighter");
    const titled = calcStats({ cls: "fighter", level: 55, base: classStats.fighter[54], slots: {}, sets: [], skills: passiveSkills("fighter", 55, passives),
      title: titleLines(["maxHp 20", "speed 5%"]),
      scrolls: [{ times: 3, effects: [{ type: "statup", stats: [{ name: "speed", value: { value: 10, relative: true } }] }] }] });
    expect(value(titled, "maxhp") - value(plain, "maxhp")).toBe(20);
    expect(value(titled, "speed")).toBeCloseTo(6 * (1 + 0.35), 5); // the title's 5 % and the third-grade scroll's 3 × 10 %
  });
});
