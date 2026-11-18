import { describe, expect, it } from "vitest";

import { classesOf, clientStigmas, family, mergeNeeds, mergeStigmas, type DbSkill, type DbStone, type GitStigma } from "./merge";

const git: GitStigma = {
  id: "kn_breakpower", faction: "daeva", advanced: false, kind: "Normal", target: "Selected Target", info: [],
  levels: [
    { level: 34, skill: 410, name: "Break Power I", text: "Inflicts 16~20 physical damage", mp: "57 MP", cast: "Cast Instantly", cooldown: "16", shards: 102, ap: 0 },
    { level: 40, skill: 457, name: "Break Power II", text: "Inflicts 16~20 physical damage", mp: "61 MP", cast: "Cast Instantly", cooldown: "16", shards: 120, ap: 0 },
  ],
};
const skills: DbSkill[] = [
  { id: 410, internal_name: "KN_BreakPower_G1", name: "Подрубка I", description: "Наносит [%e1.MinDamage] урона", damage: "Наносит 16-20 урона", icon: "skills/kn_breakpower_g1" },
  { id: 457, internal_name: "KN_BreakPower_G2", name: null, description: "Наносит [%e1.MinDamage] урона", damage: null, icon: null },
];
const stones: DbStone[] = [
  { item_id: 140000034, skill_id: 410, internal_name: "KN_BreakPower_G1", level: 34, name: "Подрубка I", description: null, damage: null, icon: "skills/kn_breakpower_g1" },
  { item_id: 140000366, skill_id: 2055, internal_name: "KN_BreakPower_G4", level: 52, name: "Подрубка IV", description: "Наносит 20 урона", damage: "Наносит 18-22 урона", icon: "skills/kn_breakpower_g4" },
  { item_id: 140000999, skill_id: 9999, internal_name: "KN_Other_G1", level: 30, name: "Другое", description: null, damage: null, icon: null },
];

describe("a stigma's family in pulse.db", () => {
  it("is the client's skill name in lower case without the level", () => {
    expect(family("KN_BreakPower_G4")).toBe("kn_breakpower");
    expect(family("RA_BlazingTrap_Light_G2")).toBe("ra_blazingtrap_light");
  });
});

describe("the calculator's data first, then pulse.db", () => {
  const [s] = mergeStigmas([git], skills, stones);

  it("takes the Russian name and the text with the server's numbers from the database", () => {
    expect(s.levels[0].name).toBe("Подрубка I");
    expect(s.levels[0].text).toBe("Наносит 16-20 урона");
    expect(s.levels[0].icon).toBe("skills/kn_breakpower_g1");
    expect(s.levels[0].stone).toBe(140000034);
  });

  it("keeps the calculator's English when the database has no name or only a text with blanks", () => {
    expect(s.levels[1].name).toBe("Break Power II");
    expect(s.levels[1].text).toBe("Inflicts 16~20 physical damage");
  });

  it("borrows another level's icon when a level has none", () => {
    expect(s.levels[1].icon).toBe("skills/kn_breakpower_g1");
  });

  it("keeps the calculator's costs and times", () => {
    expect(s.levels[0]).toMatchObject({ shards: 102, mp: "57 MP", cooldown: "16" });
  });

  it("adds the levels only the database has, at the stone's level, with an unknown price", () => {
    expect(s.levels.map((l) => l.level)).toEqual([34, 40, 52]);
    expect(s.levels[2]).toMatchObject({ skill: 2055, name: "Подрубка IV", text: "Наносит 18-22 урона", shards: null, ap: 0, stone: 140000366, fromDb: true });
  });

  it("does not add a database level at a level the calculator already has", () => {
    const [again] = mergeStigmas([git], skills, [...stones, { ...stones[1], skill_id: 2056, level: 40 }]);
    expect(again.levels.map((l) => l.level)).toEqual([34, 40, 52]);
  });
});

describe("pulse.db mends the calculator's data", () => {
  it("replaces a level's skill id that names another skill with the stone of the same stigma at that level", () => {
    const wrong: GitStigma = { ...git, levels: [...git.levels, { ...git.levels[1], level: 52, skill: 111, name: "Break Power IV" }] };
    const [s] = mergeStigmas([wrong], [...skills, { id: 111, internal_name: "P_StatBoostBlock_G1", name: "Блок", description: null, damage: null, icon: "x" }], stones);
    expect(s.levels.map((l) => [l.level, l.skill])).toEqual([[34, 410], [40, 457], [52, 2055]]);
    expect(s.levels[2]).toMatchObject({ name: "Подрубка IV", shards: 120, stone: 140000366 });
  });

  it("finds the stigma's stones by its skills' client names when the calculator's id is spelled otherwise", () => {
    const trap: GitStigma = { ...git, id: "ra_heavenstrap_dark", levels: [{ ...git.levels[0], level: 28, skill: 709 }] };
    const [s] = mergeStigmas([trap], [{ id: 709, internal_name: "RA_Dark_HeavensTrap_G1", name: "Ловушка I", description: null, damage: null, icon: "t" }],
      [{ item_id: 1, skill_id: 709, internal_name: "RA_Dark_HeavensTrap_G1", level: 28, name: "Ловушка I", description: null, damage: null, icon: "t" },
        { item_id: 2, skill_id: 2081, internal_name: "RA_Dark_HeavensTrap_G5", level: 52, name: "Ловушка V", description: null, damage: null, icon: "t" }]);
    expect(s.levels.map((l) => l.skill)).toEqual([709, 2081]);
  });
});

describe("the stigmas' needs: the calculator's, then the client's", () => {
  const lvl = (skill: number) => ({ level: 20, skill, name: "", text: "", mp: "", cast: "", cooldown: "", shards: 1, ap: 0 });
  const st = (id: string, skill: number): GitStigma => ({ id, faction: "daeva", advanced: false, kind: "", target: "", info: [], levels: [lvl(skill)] });
  const git = [st("el_sleepingspirit", 1), st("el_bind", 2), st("el_silence", 3), st("el_burst", 4), st("el_other", 5)];
  const skills: DbSkill[] = [[1, "EL_SleepingSpirit_G1"], [2, "EL_Bind_G1"], [3, "EL_Silence_G1"], [4, "EL_EnchantmentBurst_G1"], [5, "EL_Other_G1"]]
    .map(([id, internal_name]) => ({ id: id as number, internal_name: internal_name as string, name: null, description: null, damage: null, icon: null }));
  const stone = (skill_id: number, internal_name: string, requires: string | null): DbStone =>
    ({ item_id: skill_id + 100, skill_id, internal_name, level: 20, name: null, description: null, damage: null, icon: null, requires });

  it("takes a stigma's needs from its stone in the client when every one of them is a stigma of the class", () => {
    const needs = mergeNeeds(git, [["el_sleepingspirit", "el_bind"], ["el_sleepingspirit", "el_burst"], ["el_other", "el_bind"]], skills,
      [stone(1, "EL_SleepingSpirit_G1", '[["EL_Silence_G1", 3, 1], ["EL_EnchantmentBurst_G1, EL_EnchantmentBurst_G2", null, 1]]'), stone(5, "EL_Other_G1", null)]);
    expect(needs).toEqual([["el_sleepingspirit", "el_silence"], ["el_sleepingspirit", "el_burst"], ["el_other", "el_bind"]]);
  });

  it("keeps the calculator's needs when the client names a stigma the class does not have", () => {
    const needs = mergeNeeds(git, [["el_sleepingspirit", "el_bind"]], skills, [stone(1, "EL_SleepingSpirit_G1", '[["EL_Unknown_G1", null, 1]]')]);
    expect(needs).toEqual([["el_sleepingspirit", "el_bind"]]);
  });
});

describe("the stone's own numbers from the client", () => {
  it("adds the kinah price to every level and fills the shards and abyss points the calculator lacks", () => {
    const [s] = mergeStigmas([git], skills, stones.map((st) => ({ ...st, price: 3840, shards: st.skill_id === 2055 ? 270 : 999, ap: 0 })));
    expect(s.levels.map((l) => [l.level, l.shards, l.price])).toEqual([[34, 102, 3840], [40, 120, null], [52, 270, 3840]]);
  });
});

describe("a stone's classes", () => {
  it("reads the client's columns, a base class meaning both of its classes, and keeps a class skill to its own class", () => {
    expect(classesOf('{"priest": 51}', "PR_Stigma_Suggestion_G2")).toEqual({ cleric: 51 });
    expect(classesOf('{"warrior": 20, "fighter": 20}', "Stigma_Heal_G2")).toEqual({ fighter: 20, knight: 20 });
    expect(classesOf('{"assassin": 48}', "AS_InstantRecall_G1")).toEqual({ assassin: 48 });
    expect(classesOf(null, "AS_X_G1")).toEqual({});
  });
});

describe("the stigmas only the client has", () => {
  const stone = (item_id: number, skill_id: number, internal_name: string, level: number, more: Partial<DbStone> = {}): DbStone => ({
    item_id, skill_id, internal_name, level, name: internal_name, description: null, damage: "Урон 10", icon: "i", requires: null,
    classes: `{"assassin": ${level}}`, races: "pc_light pc_dark", shards: 144, ap: null, price: 3840, advanced: 0, ...more });
  const claimed: GitStigma = { ...git, id: "as_ambush", levels: [{ ...git.levels[0], skill: 1 }] };
  const known: DbSkill[] = [{ id: 1, internal_name: "AS_Ambush_G1", name: null, description: null, damage: null, icon: null }];

  it("lists the stones of the class no calculator stigma claims, one stigma per client skill without its level", () => {
    const out = clientStigmas("assassin", "elyos", [claimed], known, [
      stone(10, 1, "AS_Ambush_G1", 20), stone(11, 937, "AS_InstantRecall_G1", 48), stone(12, 938, "AS_InstantRecall_G2", 54),
      stone(13, 939, "KN_Other_G1", 30, { classes: '{"knight": 30}' }), stone(14, 940, "AS_Dark_G1", 30, { races: "pc_dark" })]);
    expect(out.map((s) => s.id)).toEqual(["as_instantrecall"]);
    expect(out[0]).toMatchObject({ faction: "daeva", advanced: false, onlyClient: true });
    expect(out[0].levels.map((l) => [l.level, l.skill, l.shards, l.price, l.stone, l.text])).toEqual([
      [48, 937, 144, 3840, 11, "Урон 10"], [54, 938, 144, 3840, 12, "Урон 10"]]);
  });

  it("shows the client's description with its blanks dotted when the database has no resolved text", () => {
    const [s] = clientStigmas("assassin", "elyos", [], [], [stone(11, 937, "AS_InstantRecall_G1", 48, { damage: null, description: "Отходит на [%e1.Range] м." })]);
    expect(s.levels[0].text).toBe("Отходит на … м.");
  });

  it("keeps the faction and the advanced mark of the stone", () => {
    const [s] = clientStigmas("assassin", "asmodian", [], [], [stone(14, 940, "AS_Dark_G1", 30, { races: "pc_dark", advanced: 1, ap: 5000 })]);
    expect(s).toMatchObject({ id: "as_dark", faction: "asmodian", advanced: true });
    expect(s.levels[0].ap).toBe(5000);
  });
});
