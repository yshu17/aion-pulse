/**
 * The gear calculator's arithmetic for Aion Classic 2.0 (docs/GEAR_CALC_PLAN.md): the same steps as aiongear.fun's eu20
 * calculator (its functions Fv, Iv, Ov, Lv, R3 and the value component), written again for Pulse+'s own data.
 *
 *   const stats = calcStats({ cls: "fighter", level: 55, slots, skills: passiveSkills("fighter", 55, data) })
 *   shown(stats.get("maxhp"))  -> 7318
 *
 * A stat is { basic, bonus }: «basic» the character's and the items' own numbers, «bonus» what bonuses, stones, sets and
 * skills add. Units are the game's: speeds and ranges in thousandths, percent stats (PvP, damage reduction, enmity) in tenths.
 */

export type StatMap = Map<string, { basic: number; bonus: number }>;
export type Line = [stat: string, value: number, percent: boolean];

export interface GearItem {
  id: number; name: string; icon: string; grade: string; level: number; slot: string; grp: string;
  classes: string[]; basic: Record<string, number>; bonus: Line[]; stones: number | null; stonesBonus: number | null;
  enchant: boolean; setId: number | null;
}
export interface Stone { id: number; name: string; icon: string; grade: string; level: number; stat: string; value: number }
export interface GearSet { id: number; name: string; items: number[]; bonuses: { need: number; stats: Line[] }[] }
export interface Equipped { item: GearItem; enchant: number; stones: (Stone | null)[] }
export type SlotKey = "main" | "sub" | "head" | "torso" | "pants" | "shoulder" | "glove" | "shoes" | "earring1" | "earring2"
  | "ring1" | "ring2" | "necklace" | "belt" | "wing";

export interface BaseRow {
  power: number; health: number; agility: number; accuracy: number; knowledge: number; will: number; hp: number; mp: number;
  evasion: number; physicalAccuracy: number; magicalAccuracy: number;
}
export interface Effect { type: string; [k: string]: any }
export interface Skill { id: number; name: string; effects: Effect[] }

const ONE_HAND = new Set(["sword", "dagger", "mace", "shield"]);
const MAGIC_HAND = new Set(["spellbook", "orb"]);
const SPEEDS = ["attackdelay", "boostcastingtime", "speed", "flyspeed", "allspeed"];

/** The enchant bonus per level for versions under 3.0 (aiongear's table Dv): every level up to the key adds its numbers. */
const ARMOUR_ENCHANT: Record<string, Record<string, number>> = {
  rb_torso: { physicaldefend: 3, maxhp: 14, physicalcriticalreducerate: 4 }, rb_pants: { physicaldefend: 2, maxhp: 12, physicalcriticalreducerate: 3 },
  rb_shoulder: { physicaldefend: 1, maxhp: 10, physicalcriticalreducerate: 2 }, rb_glove: { physicaldefend: 1, maxhp: 10, physicalcriticalreducerate: 2 },
  rb_shoes: { physicaldefend: 1, maxhp: 10, physicalcriticalreducerate: 2 },
  lt_torso: { physicaldefend: 4, maxhp: 12, physicalcriticalreducerate: 4 }, lt_pants: { physicaldefend: 3, maxhp: 10, physicalcriticalreducerate: 3 },
  lt_shoulder: { physicaldefend: 2, maxhp: 8, physicalcriticalreducerate: 2 }, lt_glove: { physicaldefend: 2, maxhp: 8, physicalcriticalreducerate: 2 },
  lt_shoes: { physicaldefend: 2, maxhp: 8, physicalcriticalreducerate: 2 },
  ch_torso: { physicaldefend: 5, maxhp: 10, physicalcriticalreducerate: 4 }, ch_pants: { physicaldefend: 4, maxhp: 8, physicalcriticalreducerate: 3 },
  ch_shoulder: { physicaldefend: 3, maxhp: 6, physicalcriticalreducerate: 2 }, ch_glove: { physicaldefend: 3, maxhp: 6, physicalcriticalreducerate: 2 },
  ch_shoes: { physicaldefend: 3, maxhp: 6, physicalcriticalreducerate: 2 },
  pl_torso: { physicaldefend: 6, maxhp: 8, physicalcriticalreducerate: 4 }, pl_pants: { physicaldefend: 5, maxhp: 6, physicalcriticalreducerate: 3 },
  pl_shoulder: { physicaldefend: 4, maxhp: 4, physicalcriticalreducerate: 2 }, pl_glove: { physicaldefend: 4, maxhp: 4, physicalcriticalreducerate: 2 },
  pl_shoes: { physicaldefend: 4, maxhp: 4, physicalcriticalreducerate: 2 },
};
const WEAPON_ENCHANT: Record<string, Record<string, number>> = {
  sword: { damage: 2 }, greatsword: { damage: 4 }, dagger: { damage: 2 }, mace: { damage: 3, magicalskillboost: 20 },
  orb: { damage: 3, magicalskillboost: 20 }, spellbook: { damage: 3, magicalskillboost: 20 }, polearm: { damage: 4 },
  staff: { damage: 3, magicalskillboost: 20 }, bow: { damage: 4 },
};

/** Only weapons, shields and the five armour pieces take an enchant in 2.0: not the head, the jewellery, the belt or the wings. */
export function canEnchant(item: GearItem): boolean {
  return item.enchant && (item.grp === "shield" || item.grp in WEAPON_ENCHANT || item.grp in ARMOUR_ENCHANT);
}

/** What `level` enchant levels add to an item of this group: name -> value. */
export function enchantBonus(grp: string, level: number): Record<string, number> {
  const out: Record<string, number> = {};
  for (let s = 0; s < level; s++) {
    const step = grp === "shield" ? (s < 10 ? { damagereduce: 2 } : { block: 30 }) : WEAPON_ENCHANT[grp] ?? ARMOUR_ENCHANT[grp];
    if (!step) return out;
    for (const [k, v] of Object.entries(step)) out[k] = (out[k] ?? 0) + v;
  }
  return out;
}

/** A combined stat: what it stands for («phyattack» is damage, «allspeed» both speeds …). */
export function expand(stat: string): string[] {
  switch (stat) {
    case "elementaldefendall": return ["elementaldefendair", "elementaldefendearth", "elementaldefendfire", "elementaldefendwater"];
    case "allspeed": return ["speed", "flyspeed"];
    case "activedefend": return ["parry", "dodge", "block"];
    case "phyattack": case "magicalattack": return ["damage"];
    case "pvpattackratio": return ["pvpattackratiomagical", "pvpattackratiophysical"];
    case "pvpdefendratio": return ["pvpdefendratiomagical", "pvpdefendratiophysical"];
    case "speedratio": return ["speed"];
    case "attackdelayratio": return ["attackdelay"];
    case "boostcastingtimeratio": return ["boostcastingtime"];
    default: return [stat];
  }
}

/** «magicalattack» counts only with a book or an orb in the main hand, «phyattack» only without one. */
function ignored(stat: string, main: GearItem | undefined): boolean {
  return (stat === "magicalattack" && (!main || !MAGIC_HAND.has(main.grp))) || (stat === "phyattack" && !!main && MAGIC_HAND.has(main.grp));
}

const add = (o: Record<string, number>, k: string, v: number) => { o[k] = (o[k] ?? 0) + v; };

/** The class's numbers at the level (aiongear's Fv). */
export function baseStats(cls: string, row: BaseRow, level: number): Record<string, number> {
  const s: Record<string, number> = {
    str: row.power, vit: row.health, agi: row.agility, acc: row.accuracy, int: row.knowledge, wis: row.will, maxhp: row.hp, maxmp: row.mp,
    maxfp: 60, dodge: row.evasion, block: row.evasion, parry: row.evasion, hitaccuracy: row.physicalAccuracy,
    magicalhitaccuracy: row.magicalAccuracy, speed: 6000, flyspeed: 9000, attackdelay: 1500, magicalcriticalreducerate: 0,
    magicalcritical: 50, boostcastingtime: 1000, physicalcriticalreducerate: 0,
  };
  s.critical = cls === "chanter" ? 1 : ["assassin", "ranger"].includes(cls) ? 3 : 2;
  if (["wizard", "elementalist", "cleric"].includes(cls)) s.magicalcriticalreducerate = 50;
  if (level > 50) s.physicalcriticalreducerate = (level - 50) * 6;
  return s;
}

const avgDamage = (w: GearItem) => ((w.basic.mindamage ?? 0) + (w.basic.maxdamage ?? 0)) / 2;

/** The second weapon's share (aiongear's Mp): 0.825 + 0.025 × the dual-wield mastery's grade (+1 for the assassin). */
export function dualFactor(cls: string, skills: Skill[]): number {
  const dual = skills.find((s) => /^p_equip_dual_g/i.test(s.name));
  let n = dual ? Number(dual.name.slice(-1)) || 1 : 1;
  if (cls === "assassin") n += 1;
  return 0.825 + n * 0.025;
}

/** A weapon's attack from power (knowledge for a book or an orb), with its enchant. */
function weaponDamage(w: Equipped, power: number, knowledge: number): number {
  const enchant = enchantBonus(w.item.grp, w.enchant).damage ?? 0;
  return (avgDamage(w.item) + enchant) * ((MAGIC_HAND.has(w.item.grp) ? knowledge : power) / 100);
}

/** The weapon mastery's share of the weapon's attack (aiongear's Ev). */
function masteryDamage(w: Equipped | undefined, skills: Skill[]): number {
  if (!w) return 0;
  const weapon = { sword: "1h_sword", mace: "1h_mace", dagger: "1h_dagger", orb: "2h_orb", spellbook: "2h_book", greatsword: "2h_sword",
    polearm: "2h_polearm", staff: "2h_staff", bow: "bow" }[w.item.grp];
  let pct = 0;
  for (const s of skills) for (const e of s.effects) if (e.type === "wpn_mastery" && e.weapon === weapon) pct = e.value?.value ?? 0;
  const enchant = enchantBonus(w.item.grp, w.enchant).damage ?? 0;
  return (avgDamage(w.item) + enchant) * (pct / 100);
}

/** A scroll in use: its effects count `times` its grade (aiongear's Pv: the bonus × the scroll's level). */
export interface ScrollUse { effects: Effect[]; times: number }

export interface CalcInput {
  cls: string; level: number; base: BaseRow; slots: Partial<Record<SlotKey, Equipped>>; sets: GearSet[];
  skills: Skill[];          // the class's passive skills and the buffs in use
  scrolls?: ScrollUse[];
  title?: Line[];           // the title's bonus lines
}

export function calcStats(input: CalcInput): StatMap {
  const { cls, level, slots, skills } = input;
  const stats: StatMap = new Map();
  const setBasic = (o: Record<string, number>) => { for (const [k, v] of Object.entries(o)) { const s = stats.get(k) ?? { basic: 0, bonus: 0 }; s.basic = v; stats.set(k, s); } };
  const addBonus = (o: Record<string, number>) => { for (const [k, v] of Object.entries(o)) { const s = stats.get(k) ?? { basic: 0, bonus: 0 }; s.bonus += v; stats.set(k, s); } };
  const main = slots.main;
  const subAny = slots.sub;
  const sub = subAny && subAny.item.grp !== "shield" ? subAny : undefined; // a second weapon, not a shield
  const subOneHand = !!sub && ONE_HAND.has(sub.item.grp);
  const worn = Object.entries(slots).filter(([, e]) => e) as [SlotKey, Equipped][];

  // 1. the class at the level
  setBasic(baseStats(cls, input.base, level));
  const baseOf = (k: string) => stats.get(k)?.basic ?? 0;

  // 2. the items' own numbers, their enchant, the attack (aiongear's Iv, k3, M3)
  {
    const a: Record<string, number> = {};
    for (const [k, s] of stats) a[k] = s.basic;
    for (const [slot, e] of worn) {
      if ((slot === "main" || slot === "sub") && e.item.grp !== "shield") continue;
      for (const [k, v] of Object.entries(e.item.basic)) add(a, k, v);
      if (e.enchant > 0) for (const [k, v] of Object.entries(enchantBonus(e.item.grp, e.enchant))) add(a, k, v);
    }
    let delay = a.attackdelay ?? 0;
    if (main) delay = main.item.basic.attackdelay ?? delay;
    else if (sub) delay = sub.item.basic.attackdelay ?? delay;
    if (main && sub && ONE_HAND.has(main.item.grp) && subOneHand && sub.item.basic.attackdelay) delay += sub.item.basic.attackdelay / 4;
    a.attackdelay = delay;
    const power = baseOf("str"), knowledge = baseOf("int"), accuracy = baseOf("hitaccuracy"), critical = baseOf("critical");
    const att: Record<string, number> = { r_damage: Math.floor(18 * power / 100), r_hitaccuracy: accuracy, r_critical: critical, l_damage: 0,
      l_hitaccuracy: 0, l_critical: 0, magicalskillboost: 0, magicalhitaccuracy: 0 };
    if (main) {
      const crit = main.item.basic.critical ?? 0;
      att.r_damage = weaponDamage(main, power, knowledge);
      att.r_hitaccuracy += main.item.basic.hitaccuracy ?? 0;
      att.r_critical += crit; // the site adds an orb's or a book's crit here too
      att.magicalhitaccuracy += main.item.basic.magicalaccuracy ?? 0;
      const boost = (main.item.basic.magicalskillboost ?? 0) + (main.enchant > 0 ? enchantBonus(main.item.grp, main.enchant).magicalskillboost ?? 0 : 0);
      if (main.item.basic.magicalskillboost !== undefined) att.magicalskillboost = boost;
      for (const [k, v] of Object.entries(main.item.basic)) {
        if (!["mindamage", "maxdamage", "hitaccuracy", "magicalaccuracy", "critical", "attackdelay", "magicalskillboost"].includes(k)) att[k] = v;
      }
    }
    if (sub && subOneHand) {
      att.l_damage = weaponDamage(sub, power, knowledge) * dualFactor(cls, skills);
      att.l_hitaccuracy = accuracy + (sub.item.basic.hitaccuracy ?? 0);
      att.l_critical = critical + (sub.item.basic.critical ?? 0);
    }
    for (const [k, s] of stats) if (k in att) att[k] += s.basic;
    setBasic({ ...a, ...att });
  }

  // 3. bonuses: the items' lines, the stones, the sets; the weapons' speed and PvP from the better hand (aiongear's Ov, P3, E3, A3)
  {
    const b: Record<string, number> = { physicaldefend: 0 };
    let armourDefence = 0, armourPct = 0;
    const handOnly = ["attackdelay", "boostcastingtime", "pvpattackratio", "pvpattackratiomagical", "pvpattackratiophysical"];
    for (const [slot, e] of worn) {
      const weapon = (slot === "main" || slot === "sub") && e.item.grp !== "shield";
      for (const [stat, value] of e.item.bonus) {
        if (weapon && handOnly.includes(stat)) continue;
        if (ignored(stat, main?.item)) continue;
        for (const k of expand(stat)) add(b, k, value); // the site adds the number as it is, «10%» of a speed is 10
      }
      if (/^(rb|lt|ch|pl)_/.test(e.item.grp)) {
        armourDefence += e.item.basic.physicaldefend ?? 0;
        armourPct += e.item.grp.endsWith("_torso") ? 5 : 2;
      }
      for (const stone of e.stones) if (stone && !ignored(stone.stat, main?.item)) for (const k of expand(stone.stat)) add(b, k, stone.value);
    }
    // the hands: the better attack speed and casting speed, PvP attack
    let delay = 0, cast = 0, pvp = 0;
    const handBonus = (e: Equipped | undefined, stat: string) => e?.item.bonus.find(([s]) => s === stat)?.[1] ?? 0;
    if (main) { delay = handBonus(main, "attackdelay"); cast = handBonus(main, "boostcastingtime"); pvp = handBonus(main, "pvpattackratio"); }
    if (sub) {
      delay = Math.max(delay, handBonus(sub, "attackdelay")); cast = Math.max(cast, handBonus(sub, "boostcastingtime"));
      // before 3.0 two one-handed weapons add their PvP attack up; otherwise the better one counts
      pvp = subOneHand ? pvp + handBonus(sub, "pvpattackratio") : Math.max(pvp, handBonus(sub, "pvpattackratio"));
    }
    if (delay) add(b, "attackdelay", delay);
    if (cast) add(b, "boostcastingtime", cast);
    if (pvp) { add(b, "pvpattackratio", pvp); add(b, "pvpattackratiomagical", pvp); add(b, "pvpattackratiophysical", pvp); }
    // the sets: a bonus of n pieces when n are worn, the whole-set one when all are
    const counted = new Map<number, number>();
    const seen = new Set<number>();
    for (const [, e] of worn) if (e.item.setId !== null && !seen.has(e.item.id)) { seen.add(e.item.id); counted.set(e.item.setId, (counted.get(e.item.setId) ?? 0) + 1); }
    for (const [id, n] of counted) {
      const set = input.sets.find((s) => s.id === id);
      if (!set) continue;
      for (const bonus of set.bonuses) {
        if ((bonus.need === 0 && n < set.items.length) || bonus.need > n) continue;
        for (const [stat, value] of bonus.stats) if (!ignored(stat, main?.item)) for (const k of expand(stat)) add(b, k, value);
      }
    }
    b.physicaldefend += armourDefence * (armourPct / 100);
    const dmg = b.damage ?? 0, hit = b.hitaccuracy ?? 0, crit = b.critical ?? 0;
    delete b.damage; delete b.hitaccuracy; delete b.critical;
    b.r_damage = dmg + masteryDamage(main, skills); b.r_hitaccuracy = hit; b.r_critical = crit;
    if (sub && subOneHand) {
      const f = dualFactor(cls, skills);
      b.l_damage = (dmg + masteryDamage(sub, skills) * f) * f; b.l_hitaccuracy = hit; b.l_critical = crit;
    }
    addBonus(b);
  }

  // 4. the skills (passive ones and the buffs): their stat effects on the basic numbers (aiongear's Lv / Jo)
  addBonus(skillBonus(skills, stats, main?.item, sub?.item));
  // the scrolls (aiongear's Pv) and the title (Rv)
  for (const scroll of input.scrolls ?? []) {
    const b = skillBonus([{ id: 0, name: "scroll", effects: scroll.effects }], stats, main?.item, sub?.item);
    addBonus(Object.fromEntries(Object.entries(b).map(([k, v]) => [k, v * scroll.times])));
  }
  if (input.title?.length) {
    const t: Record<string, number> = {};
    for (const [stat, value] of input.title) if (!ignored(stat, main?.item)) for (const k of targets(stat, sub?.item)) add(t, k, value);
    addBonus(t);
  }

  // 5. the game's limits on the speeds
  for (const [k, s] of stats) {
    const limit = { attackdelay: [-95, 50], boostcastingtime: [-95, 75], speed: [-95, 100], flyspeed: [-95, 77.77777] }[k];
    if (limit) s.bonus = Math.min(Math.max(s.bonus, limit[0]), limit[1]);
  }
  return stats;
}

/** The names a stat's skill bonus lands on: damage, accuracy and crit go to the right hand (and the left one with a second weapon). */
function targets(stat: string, sub: GearItem | undefined): string[] {
  const out: string[] = [];
  for (const k of expand(stat)) {
    if (["damage", "hitaccuracy", "critical"].includes(k)) { out.push(`r_${k}`); if (sub && ONE_HAND.has(sub.grp)) out.push(`l_${k}`); continue; }
    out.push(k);
  }
  return out;
}

const relativeValue = (basic: number, value: { value: number; relative?: boolean }) => (value.relative ? (value.value / 100) * basic : value.value);

/** The stat effects of the skills (statup, statboost, boosthate, weapon stat up, aura, provoker), on the basic numbers. */
export function skillBonus(skills: Skill[], stats: StatMap, main: GearItem | undefined, sub: GearItem | undefined): Record<string, number> {
  const out: Record<string, number> = {};
  const basic = (k: string) => stats.get(k)?.basic ?? 0;
  const weaponName = (g?: GearItem) => g && ({ sword: "1h_sword", mace: "1h_mace", dagger: "1h_dagger", orb: "2h_orb", spellbook: "2h_book",
    greatsword: "2h_sword", polearm: "2h_polearm", staff: "2h_staff", bow: "bow" } as Record<string, string>)[g.grp];
  const effect = (e: Effect) => {
    if (e.f || e.flying) return;
    const value = (v: any, stat: string) => ({ ...v, relative: SPEEDS.includes(stat) ? false : v?.relative });
    const put = (stat: string, v: any, sign = 1) => { for (const k of targets(stat, sub)) if (!ignored(k, main)) add(out, k, sign * relativeValue(basic(k), value(v, stat))); };
    switch (e.type) {
      case "boosthate": put("boosthate", e.value); break;
      case "statboost": put(e.stat, e.value); break;
      case "slow": put("attackdelay", e.value); break;
      case "weaponstatup": case "weaponstatboost":
        if (e.weapon === weaponName(main)) put(e.stat, e.stat === "attackrange" && !e.value?.relative ? { ...e.value, value: e.value.value * 1000 } : e.value);
        break;
      case "statup": for (const s of e.stats ?? []) put(s.name ?? s.stat, s.value); break;
      case "statdown": for (const s of e.stats ?? []) put(s.name ?? s.stat, s.value, -1); break;
      case "aura": for (const inner of e.effects ?? []) effect(inner); break;
      case "provoker": for (const inner of e.effects ?? []) effect(inner); break;
    }
  };
  for (const s of skills) for (const e of s.effects) effect(e);
  return out;
}

export function isPercentStat(name: string): boolean {
  return ["damagereduce", "boosthate", "pvpattackratio", "pvpattackratiomagical", "pvpattackratiophysical", "pvpdefendratio",
    "pvpdefendratiomagical", "pvpdefendratiophysical", "pveattackratio", "pvedefendratio", "allattackratio", "alldefendratio"].includes(name);
}
export function isRelativeStat(name: string): boolean {
  return ["attackdelay", "boostcastingtime", "speed", "flyspeed", "attackrange"].includes(name);
}

/** The number the game shows (aiongear's calcAbsoluteValue): percent stats in tenths, speeds and ranges in thousandths. */
export function shown(name: string, s: { basic: number; bonus: number } | undefined): number {
  if (!s) return 0;
  let v = s.basic;
  if (isPercentStat(name)) return v / 10 + s.bonus / 10;
  if (isRelativeStat(name)) {
    let d = (s.bonus / 100) * v;
    if (name === "attackrange") d = s.bonus;
    v = ["attackdelay", "boostcastingtime"].includes(name) ? v - d : v + d;
    return v / 1000;
  }
  return v + s.bonus;
}

/** The class's passive skills at the level (the last level of the table at or under it), as aiongear lists them. */
export function passiveSkills(cls: string, level: number, table: { skills: Record<string, any>; class_skill_ids: Record<string, Record<string, number[]>> }): Skill[] {
  const byLevel = table.class_skill_ids[cls] ?? {};
  const banned = cls === "ranger" ? [2300, 2304, 2308, 2312] : [];
  for (let l = level; l > 0; l--) {
    const ids = byLevel[String(l)];
    if (!ids) continue;
    return ids.filter((id) => !banned.includes(id) && !(id === 129 && cls === "fighter")).map((id) => table.skills[String(id)])
      .filter(Boolean).map((s) => ({ id: s.id, name: s.name, effects: s.effects })).sort((a, b) => a.id - b.id);
  }
  return [];
}

/** The shown number rounded as the site prints it: whole numbers, percents and speeds with up to two decimals. */
export function display(name: string, s: { basic: number; bonus: number } | undefined): number {
  const v = shown(name, s);
  return isPercentStat(name) || isRelativeStat(name) ? Math.round(v * 1000) / 1000 : Math.round(v);
}

/** A title's bonus lines from the client's «maxHp 20», «speed 10%» (pulse.db title.stats.bonus). */
export function titleLines(bonus: string[]): Line[] {
  const out: Line[] = [];
  for (const text of bonus) {
    const m = /^\s*([A-Za-z_]+)\s+(-?[\d.]+)\s*(%?)/.exec(text);
    if (m) out.push([m[1].toLowerCase(), Number(m[2]), m[3] === "%"]);
  }
  return out;
}

/** The buffs of the class and the ones other classes cast on everyone, at the character's level: the chain's last step it has. */
export interface ActiveSkill { id: number; share: boolean; chain: { level: number; name: string; icon: string | null; effects: Effect[] }[] }
export function buffAt(skill: ActiveSkill, level: number): { name: string; icon: string | null; effects: Effect[] } | null {
  const steps = skill.chain.filter((c) => c.level <= level);
  return steps.length ? steps[steps.length - 1] : null;
}

/** A scroll's grade a character of this level uses: the last one whose use level it has. */
export interface ScrollData { type: string; effects: Effect[]; levels: { level: number; minLevel: number; name: string; icon: string | null }[] }
export function scrollAt(scroll: ScrollData, level: number) {
  return scroll.levels.reduce<ScrollData["levels"][number] | null>((best, l) => (l.minLevel <= level ? l : best), null);
}
