// «Калькуляторы → Экипировка»: the gear calculator of Aion Classic 2.0 (docs/GEAR_CALC_PLAN.md), aiongear.fun's eu20 one
// in Pulse+'s look. Class and level, the doll, a picker per slot, the item's enchant and manastones, the characteristics,
// up to four gear sets and their comparison. The build is kept in this computer's storage.
import { useCallback, useEffect, useMemo, useState } from "react";

import classStats from "../../../../data/gear/eu20/class_stats.json";
import passiveTable from "../../../../data/gear/eu20/passive_skills.json";
import activeTable from "../../../../data/gear/eu20/active_skills.json";
import scrollTable from "../../../../data/gear/eu20/scrolls.json";
import { addSet, emptyBuild, KEY, MAX_SETS, readBuild, removeSet, withSet, writeBuild, type SavedBuild, type SavedSlot, stoneCap, swapWeapons } from "../../core/gear/build";
import { buffAt, calcStats, canEnchant, display, enchantBonus, passiveSkills, scrollAt, titleLines, type ActiveSkill, type BaseRow, type Equipped, type GearItem, type GearSet,
  type ScrollData, type Skill, type SlotKey, type StatMap, type Stone } from "../../core/gear/engine";
import { CLASSES, PANEL, SLOT_NAME, groupName, statName } from "../../core/gear/labels";
import { gearChoices, gearGroups, gearItem, gearSets, gearStones, gearTitles } from "../../core/db/gear";
import { RARITY } from "../../core/bestiary/card";
import type { All } from "../../core/db/npcPoints";
import { PickMenu } from "../bestiary/PickMenu";
import { CardBody, useSpec, hasStoneBlock, StoneUi } from "../ItemCard";
import { Icon } from "../Icon";
import { IconClose, IconReset, IconSearch, IconSwap } from "../icons";
import { m } from "motion/react";
import { EASE } from "../fx";
import { enchantAdds, stoneAdds, stoneSum } from "../../core/gear/stones";
import type { Block } from "../../core/items/card";
import { StonePicker } from "./StonePicker";
import { pulseDb } from "../db/pulseDb";
import "../bestiary/bestiary.css";
import "./gear.css";

const BASE = (classStats as { classes: Record<string, BaseRow[]> }).classes;
const PASSIVES = passiveTable as unknown as Parameters<typeof passiveSkills>[2];
const ACTIVE = (activeTable as unknown as { classes: Record<string, ActiveSkill[]> }).classes;
const SCROLLS = (scrollTable as unknown as { scrolls: ScrollData[] }).scrolls;
const GRADES = ["mythic", "epic", "unique", "legend", "rare", "common"];
type Title = { id: number; name: string; race: string; bonus: string[] };

/** The buffs of a set: its class's and the shared ones of other classes, at the level, as skills for the arithmetic. */
function buffsOf(ids: number[], cls: string, level: number): Skill[] {
  const out: Skill[] = [];
  for (const [owner, skills] of Object.entries(ACTIVE)) for (const skill of skills) {
    if (!ids.includes(skill.id) || (owner !== cls && !skill.share)) continue;
    const step = buffAt(skill, level);
    if (step) out.push({ id: skill.id, name: step.name, effects: step.effects });
  }
  return out;
}

const gradeRu = (g: string) => RARITY[g] ?? g;

function load(): SavedBuild {
  try { return readBuild(localStorage.getItem(KEY)); } catch { return emptyBuild(); }
}

/** The equipped items of a saved set, from the items read so far. */
function equipped(slots: SavedBuild["sets"][number]["slots"], items: Map<number, GearItem>, stones: Map<number, Stone>): Partial<Record<SlotKey, Equipped>> {
  const out: Partial<Record<SlotKey, Equipped>> = {};
  for (const [slot, s] of Object.entries(slots) as [SlotKey, SavedSlot][]) {
    const item = items.get(s.id);
    if (item) out[slot] = { item, enchant: s.enchant, stones: s.stones.map((id) => (id === null ? null : stones.get(id) ?? null)) };
  }
  return out;
}

export function GearTab() {
  const [all, setAll] = useState<All | null | undefined>(undefined);
  const [build, setBuild] = useState<SavedBuild>(load);
  const [items, setItems] = useState<Map<number, GearItem>>(new Map());
  const [stones, setStones] = useState<Stone[]>([]);
  const [sets, setSets] = useState<GearSet[]>([]);
  const [selected, setSelected] = useState<SlotKey | null>(null);
  const [picking, setPicking] = useState<SlotKey | null>(null);
  const [view, setView] = useState<"stats" | "amp" | "compare">("stats");
  const [titles, setTitles] = useState<Title[]>([]);

  useEffect(() => { pulseDb().then((db) => setAll(() => db)).catch(() => setAll(null)); }, []);
  useEffect(() => { if (all) { gearStones(all).then(setStones); gearTitles(all).then(setTitles); } }, [all]);
  useEffect(() => { try { localStorage.setItem(KEY, writeBuild(build)); } catch { /* storage closed: the build lives for this run */ } }, [build]);

  // the items the build names, read once each
  const ids = useMemo(() => [...new Set(build.sets.flatMap((s) => Object.values(s.slots).map((x) => x!.id)))], [build]);
  useEffect(() => {
    if (!all) return;
    const missing = ids.filter((id) => !items.has(id));
    if (!missing.length) return;
    Promise.all(missing.map((id) => gearItem(all, id))).then((got) => setItems((old) => {
      const next = new Map(old);
      for (const item of got) if (item) next.set(item.id, item);
      return next;
    }));
  }, [all, ids, items]);
  const setIds = useMemo(() => [...new Set([...items.values()].map((i) => i.setId).filter((v): v is number => v !== null))], [items]);
  useEffect(() => { if (all && setIds.length) gearSets(all, setIds).then(setSets); }, [all, setIds]);

  const stoneById = useMemo(() => new Map(stones.map((s) => [s.id, s])), [stones]);
  const statsOf = useCallback((index: number): StatMap => {
    const set = build.sets[index];
    const title = titles.find((t) => t.id === set.gearTitle);
    return calcStats({
      cls: build.cls, level: build.level, base: BASE[build.cls][build.level - 1], sets,
      slots: equipped(set.slots, items, stoneById),
      skills: [...passiveSkills(build.cls, build.level, PASSIVES), ...buffsOf(set.buffs ?? [], build.cls, build.level)],
      scrolls: (set.scrolls ?? []).map((type) => SCROLLS.find((x) => x.type === type)).filter((x): x is ScrollData => !!x)
        .map((x) => ({ effects: x.effects, times: scrollAt(x, build.level)?.level ?? 0 })).filter((x) => x.times > 0),
      title: title ? titleLines(title.bonus) : undefined,
    });
  }, [build, items, sets, stoneById, titles]);
  const stats = useMemo(() => statsOf(build.active), [statsOf, build.active]);
  const naked = useMemo(() => calcStats({ cls: build.cls, level: build.level, base: BASE[build.cls][build.level - 1], sets: [], slots: {},
    skills: passiveSkills(build.cls, build.level, PASSIVES) }), [build.cls, build.level]);

  const active = build.sets[build.active];
  const change = (fn: (s: SavedBuild["sets"][number]) => SavedBuild["sets"][number]) => setBuild((b) => withSet(b, b.active, fn));
  const put = (slot: SlotKey, item: GearItem) => {
    setItems((old) => new Map(old).set(item.id, item));
    change((s) => ({ ...s, slots: { ...s.slots, [slot]: { id: item.id, enchant: 0, stones: Array(item.stones ?? 0).fill(null) } } }));
    setSelected(slot);
    setPicking(null);
  };
  const swapHands = () => {
    const next = swapWeapons(active.slots, items);
    if (next) change((s) => ({ ...s, slots: next }));
  };
  const canSwap = !!swapWeapons(active.slots, items);
  const takeOff = (slot: SlotKey) => change((s) => { const slots = { ...s.slots }; delete slots[slot]; return { ...s, slots }; });
  const setSlot = (slot: SlotKey, fn: (x: SavedSlot) => SavedSlot) => change((s) => ({ ...s, slots: { ...s.slots, [slot]: fn(s.slots[slot]!) } }));
  const enchantAll = (level: number) => change((s) => ({ ...s, slots: Object.fromEntries(Object.entries(s.slots).map(([k, v]) => {
    const item = items.get(v!.id);
    return [k, { ...v!, enchant: item && canEnchant(item) ? level : 0 }];
  })) }));

  const chosen = selected ? active.slots[selected] : undefined;
  const chosenItem = chosen ? items.get(chosen.id) : undefined;

  return (
    <main className="gear">
      <div className="bst-bar gear-bar">
        <PickMenu id="gear-class" label="Класс" text={CLASSES.find(([id]) => id === build.cls)?.[1] ?? "Класс"} value={build.cls}
          onPick={(cls) => setBuild((b) => ({ ...b, cls }))} options={CLASSES.map(([id, name]): [string, string] => [name, id])} />
        <label className="gear-level">Уровень
          <input type="number" min={1} max={55} value={build.level} aria-label="Уровень персонажа"
            onChange={(e) => setBuild((b) => ({ ...b, level: Math.min(Math.max(Math.round(Number(e.target.value) || 1), 1), 55) }))} />
        </label>
        <nav className="gear-sets" aria-label="Наборы">
          {build.sets.map((s, i) => (
            <span key={i} className={`gear-set${i === build.active ? " on" : ""}`}>
              <button type="button" onClick={() => setBuild((b) => ({ ...b, active: i }))} aria-pressed={i === build.active}>{s.title}</button>
              {build.sets.length > 1 && <button type="button" className="x" aria-label={`Удалить ${s.title}`} onClick={() => setBuild((b) => removeSet(b, i))}><IconClose /></button>}
            </span>
          ))}
          {build.sets.length < MAX_SETS && <button type="button" className="gear-set add" onClick={() => setBuild(addSet)}>+ Набор</button>}
        </nav>
        <span className="spacer" />
        <PickMenu id="gear-enchant" label="Заточить всё" text="Заточить всё" value="" onPick={(v) => enchantAll(Number(v))}
          options={[0, 5, 10, 12, 15].map((n): [string, string] => [`+${n}`, String(n)])} right />
        <button type="button" className="bst-reset" onClick={() => change((s) => ({ ...s, slots: {} }))}><IconReset />Снять всё</button>
      </div>

      <div className="gear-body">
        <Doll slots={active.slots} items={items} selected={selected} onSlot={(slot, filled) => (filled ? setSelected(slot) : setPicking(slot))}
          canSwap={canSwap} onSwap={() => { swapHands(); setSelected((s) => (s === "main" ? "sub" : s === "sub" ? "main" : s)); }} />

        <section className="gear-item" aria-label="Предмет">
          {all === null && <div className="bst-empty">База игры не найдена: нет файла data/pulse.db.</div>}
          {selected && chosen && chosenItem ? <SlotPanel slot={selected} item={chosenItem} saved={chosen} stones={stones}
            onEnchant={(n) => setSlot(selected, (x) => ({ ...x, enchant: n }))}
            onStone={(i, id) => setSlot(selected, (x) => { const st = [...x.stones]; st[i] = id; return { ...x, stones: st }; })}
            onReplace={() => setPicking(selected)} onTakeOff={() => { takeOff(selected); setSelected(null); }} />
            : <div className="bst-empty">Выбери слот: пустой откроет список вещей, занятый — заточку и камни.</div>}
          {sets.length > 0 && <SetsPanel sets={sets} slots={equipped(active.slots, items, stoneById)} />}
        </section>

        <section className="gear-stats" aria-label="Характеристики">
          <div className="gear-tabs">
            <button type="button" className={view === "stats" ? "on" : ""} onClick={() => setView("stats")}>Характеристики</button>
            <button type="button" className={view === "amp" ? "on" : ""} onClick={() => setView("amp")}>Усиление</button>
            <button type="button" className={view === "compare" ? "on" : ""} onClick={() => setView("compare")} disabled={build.sets.length < 2}>Сравнение наборов</button>
          </div>
          {view === "amp" ? <AmpPanel cls={build.cls} level={build.level} set={active} titles={titles} onChange={change} />
            : view === "stats" || build.sets.length < 2 ? <StatsPanel stats={stats} naked={naked} /> : <ComparePanel build={build} statsOf={statsOf} />}
        </section>
      </div>

      {picking && all && <Picker all={all} slot={picking} cls={build.cls} level={build.level} onPick={(item) => put(picking, item)} onClose={() => setPicking(null)} />}
    </main>
  );
}

/** One characteristic: the shown number, and in green what the gear and the skills add over the bare character. */
function StatRow({ name, stats, naked, other }: { name: string; stats: StatMap; naked?: StatMap; other?: StatMap }) {
  const v = display(name, stats.get(name));
  const base = naked ? display(name, naked.get(name)) : v;
  const diff = other ? Math.round((v - display(name, other.get(name))) * 1000) / 1000 : 0;
  const pct = ["boosthate", "pvpattackratiophysical", "pvpdefendratiophysical", "damagereduce"].includes(name) ? "%" : "";
  const fmt = (n: number) => n.toLocaleString("ru-RU", { maximumFractionDigits: 3 });
  const better = name === "attackdelay" || name === "boostcastingtime" ? diff < 0 : diff > 0;
  return (
    <div className="gear-stat">
      <span>{statName(name)}</span>
      <b className={v !== base ? "up" : ""}>{fmt(v)}{pct}</b>
      {other && diff !== 0 && <em className={better ? "up" : "dn"}>{diff > 0 ? "+" : ""}{fmt(diff)}</em>}
    </div>
  );
}

function StatsPanel({ stats, naked }: { stats: StatMap; naked: StatMap }) {
  return (
    <div className="gear-lists">
      {PANEL.map((group) => (
        <div key={group.title} className="gear-list">
          <h5>{group.title}</h5>
          {group.stats.map((name) => <StatRow key={name} name={name} stats={stats} naked={naked} />)}
        </div>
      ))}
    </div>
  );
}

function ComparePanel({ build, statsOf }: { build: SavedBuild; statsOf(i: number): StatMap }) {
  const all = build.sets.map((_, i) => statsOf(i));
  const rows = PANEL.flatMap((g) => g.stats).filter((name) => new Set(all.map((s) => display(name, s.get(name)))).size > 1);
  return (
    <div className="gear-compare">
      <p className="dbt-note">Разница с активным набором «{build.sets[build.active].title}». Показаны только отличающиеся характеристики.</p>
      <div className="gear-compare-grid" style={{ gridTemplateColumns: `minmax(150px, 1.2fr) repeat(${build.sets.length}, 1fr)` }}>
        <span />{build.sets.map((s, i) => <b key={i} className={i === build.active ? "on" : ""}>{s.title}</b>)}
        {rows.map((name) => (
          <div key={name} className="gear-compare-row" style={{ display: "contents" }}>
            <span>{statName(name)}</span>
            {all.map((s, i) => <StatCell key={i} name={name} s={s} other={i === build.active ? undefined : all[build.active]} />)}
          </div>
        ))}
        {!rows.length && <span className="dbt-note" style={{ gridColumn: "1 / -1" }}>Наборы одинаковые.</span>}
      </div>
    </div>
  );
}

function StatCell({ name, s, other }: { name: string; s: StatMap; other?: StatMap }) {
  const v = display(name, s.get(name));
  const diff = other ? Math.round((v - display(name, other.get(name))) * 1000) / 1000 : 0;
  const better = name === "attackdelay" || name === "boostcastingtime" ? diff < 0 : diff > 0;
  const pct = ["boosthate", "pvpattackratiophysical", "pvpdefendratiophysical", "damagereduce"].includes(name) ? "%" : "";
  return <span className="gear-cell">{v.toLocaleString("ru-RU", { maximumFractionDigits: 3 })}{pct}{diff !== 0 && <em className={better ? "up" : "dn"}> {diff > 0 ? "+" : ""}{diff.toLocaleString("ru-RU", { maximumFractionDigits: 3 })}</em>}</span>;
}

/** The chosen slot: the game's card of the item, its enchant and its manastones. */
function SlotPanel({ slot, item, saved, stones, onEnchant, onStone, onReplace, onTakeOff }: {
  slot: SlotKey; item: GearItem; saved: SavedSlot; stones: Stone[]; onEnchant(n: number): void; onStone(i: number, id: number | null): void;
  onReplace(): void; onTakeOff(): void;
}) {
  const answer = useSpec(String(item.id));
  // the card says how high a stone the item takes («70-го уровня и ниже»); without that line, ten levels above the item
  const cap = stoneCap(answer?.spec?.blocks as { kind?: string; text?: string }[] | undefined) ?? Math.min(item.level + 10, 70);
  const fits = stones.filter((s) => s.level <= cap);
  const slots = item.stones ?? 0;
  const optional = item.stonesBonus ?? 0;
  // the stones are drawn in the card, in place of its empty squares; a card without them gets the picker above it
  const inCard = hasStoneBlock(answer?.spec?.blocks as Block[] | undefined);
  const stoneById = new Map(fits.map((x) => [x.id, x]));
  const chosen = Array.from({ length: slots }, (_, i) => saved.stones[i] ?? null);
  const picker = <StonePicker slots={slots} optional={optional} chosen={chosen} fits={fits} onStone={onStone} />;
  const adds = [...enchantAdds(canEnchant(item) && saved.enchant > 0 ? enchantBonus(item.grp, saved.enchant) : {}),
    ...stoneAdds(stoneSum(chosen.map((id) => (id === null ? null : stoneById.get(id) ?? null))))];
  return (
    <m.div className="gear-slotpanel" key={item.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, ease: EASE }}>
      <div className="gear-slotpanel-head">
        <span className="dbt-made-title">{SLOT_NAME[slot]} · {groupName(item.grp)}</span>
        <span className="spacer" />
        <button type="button" className="btn" onClick={onReplace}>Заменить</button>
        <button type="button" className="btn" onClick={onTakeOff}>Снять</button>
      </div>
      <div className="gear-tune">
        <div className="gear-enchant">
          <span>Заточка</span>
          {canEnchant(item) ? <>
            <button type="button" className="btn" onClick={() => onEnchant(Math.max(0, saved.enchant - 1))} aria-label="Меньше">−</button>
            <input type="range" min={0} max={15} value={saved.enchant} onChange={(e) => onEnchant(Number(e.target.value))} aria-label="Уровень заточки" />
            <button type="button" className="btn" onClick={() => onEnchant(Math.min(15, saved.enchant + 1))} aria-label="Больше">+</button>
            <b>+{saved.enchant}</b>
          </> : <em>{item.enchant && !canEnchant(item) ? "украшения, крылья и головные уборы не точатся" : "не точится"}</em>}
        </div>
        {slots === 0 && <div className="gear-stones"><div className="gear-stones-head"><span>Магические камни</span></div>
          <em className="gear-stones-none">{item.stones === null ? "слоты для камней не известны" : "нет слотов"}</em></div>}
        {slots > 0 && answer && !inCard && picker}
      </div>
      <StoneUi.Provider value={{ ui: slots > 0 && inCard ? picker : null, adds }}>
        <CardBody id={String(item.id)} answer={answer} className="in-db" fallback={{ name: item.name, icon: item.icon, grade: item.grade, level: item.level, kind: groupName(item.grp) }} />
      </StoneUi.Provider>
    </m.div>
  );
}

function SetsPanel({ sets, slots }: { sets: GearSet[]; slots: Partial<Record<SlotKey, Equipped>> }) {
  const worn = new Set(Object.values(slots).map((e) => e!.item.id));
  const shown = sets.filter((s) => s.items.some((id) => worn.has(id)));
  if (!shown.length) return null;
  return (
    <div className="gear-setinfo">
      {shown.map((set) => {
        const n = set.items.filter((id) => worn.has(id)).length;
        return (
          <div key={set.id} className="dbt-box">
            <h5>{set.name} · {n} из {set.items.length}</h5>
            {set.bonuses.map((b, i) => {
              const on = b.need === 0 ? n >= set.items.length : n >= b.need;
              return <p key={i} className={`gear-setline${on ? " on" : ""}`}>{b.need === 0 ? "Полный набор" : `${b.need} предм.`}: {b.stats.map(([s, v, p]) => `${statName(s)} +${v}${p ? "%" : ""}`).join(", ")}</p>;
            })}
          </div>
        );
      })}
    </div>
  );
}

/** The list of what fits a slot, with the filters of the site: type, level, grade, name. */
function Picker({ all, slot, cls, level, onPick, onClose }: { all: All; slot: SlotKey; cls: string; level: number; onPick(item: GearItem): void; onClose(): void }) {
  const [typed, setTyped] = useState("");
  const [query, setQuery] = useState("");
  const [grade, setGrade] = useState("");
  const [grp, setGrp] = useState("");
  const [minLevel, setMinLevel] = useState(Math.max(1, level - 10));
  const [rows, setRows] = useState<GearItem[] | null>(null);
  const [groups, setGroups] = useState<string[]>([]);
  useEffect(() => { const t = setTimeout(() => setQuery(typed), 160); return () => clearTimeout(t); }, [typed]);
  useEffect(() => { gearGroups(all, slot, cls).then(setGroups); }, [all, slot, cls]);
  useEffect(() => {
    let alive = true;
    setRows(null);
    gearChoices(all, slot, { cls, levelMin: minLevel, levelMax: level, grade, grp, query, limit: 300 }).then((r) => alive && setRows(r));
    return () => { alive = false; };
  }, [all, slot, cls, level, minLevel, grade, grp, query]);
  useEffect(() => { const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc); }, [onClose]);
  const summary = (i: GearItem) => {
    if (i.basic.mindamage) return `Атака ${i.basic.mindamage}–${i.basic.maxdamage}`;
    if (i.basic.physicaldefend) return `Физ. защита ${i.basic.physicaldefend}`;
    if (i.basic.block) return `Блок ${i.basic.block}`;
    if (i.basic.magicalresist) return `Маг. защита ${i.basic.magicalresist}`;
    return i.bonus.slice(0, 2).map(([s, v, p]) => `${statName(s)} +${v}${p ? "%" : ""}`).join(", ");
  };
  return (
    <div className="gear-modal" role="dialog" aria-label={`Выбор: ${SLOT_NAME[slot]}`} onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="gear-picker">
        <div className="gear-picker-head">
          <b>{SLOT_NAME[slot]}</b>
          <span className="spacer" />
          <button type="button" className="ic-x btn" aria-label="Закрыть" onClick={onClose}><IconClose /></button>
        </div>
        <div className="bst-bar">
          <div className="bst-search">
            <IconSearch />
            <input className="field" autoFocus placeholder="Поиск по названию или ID…" value={typed} onChange={(e) => setTyped(e.target.value)} aria-label="Поиск предмета" />
          </div>
          {groups.length > 1 && <PickMenu id="gear-grp" label="Тип" text={grp ? groupName(grp) : "Тип"} lit={!!grp} value={grp} onPick={setGrp}
            options={[["Все", ""], ...groups.map((g): [string, string] => [groupName(g), g])]} />}
          <PickMenu id="gear-grade" label="Качество" text={grade ? gradeRu(grade) : "Качество"} lit={!!grade} value={grade} onPick={setGrade}
            options={[["Любое", ""], ...GRADES.map((g): [string, string] => [gradeRu(g), g])]} />
          <label className="gear-level">Ур. от
            <input type="number" min={1} max={level} value={minLevel} onChange={(e) => setMinLevel(Math.min(Math.max(Number(e.target.value) || 1, 1), level))} />
            до {level}
          </label>
        </div>
        <ul className="gear-choices">
          {rows === null ? <li className="dbt-note">Загружаю…</li> : !rows.length ? <li className="dbt-note">Ничего не нашлось: сбрось фильтры.</li>
            : rows.map((i) => (
              <li key={i.id}>
                <button type="button" onClick={() => onPick(i)}>
                  <span className="lvl">{i.level}</span>
                  <Icon name={i.icon} size={32} />
                  <span className={`nm g-${i.grade}`}>{i.name}</span>
                  <span className="grp">{groupName(i.grp)}</span>
                  <span className="sum">{summary(i)}</span>
                </button>
              </li>
            ))}
        </ul>
      </div>
    </div>
  );
}

/** The doll as the game's character window has it: the weapons and the wings on top, six slots down each side. */
const DOLL_LAYOUT: { slot: SlotKey; area: string; hint: string }[] = [ // row by row: Tab goes the way the eye does
  { slot: "main", area: "main", hint: "icon_item_sword_c01" }, { slot: "wing", area: "wing", hint: "icon_item_wing01" },
  { slot: "sub", area: "sub", hint: "icon_item_shield_c01" },
  { slot: "head", area: "l1", hint: "icon_item_pl_head_c01a" }, { slot: "necklace", area: "r1", hint: "icon_item_necklace_c01" },
  { slot: "earring1", area: "l2", hint: "icon_item_earring_c01" }, { slot: "earring2", area: "r2", hint: "icon_item_earring_c01" },
  { slot: "torso", area: "l3", hint: "icon_item_pl_torso_c01" }, { slot: "shoulder", area: "r3", hint: "icon_item_pl_shoulder_c01" },
  { slot: "pants", area: "l4", hint: "icon_item_pl_pants_c01" }, { slot: "glove", area: "r4", hint: "icon_item_pl_glove_c01" },
  { slot: "ring1", area: "l5", hint: "icon_item_ring_c01" }, { slot: "ring2", area: "r5", hint: "icon_item_ring_c01" },
  { slot: "shoes", area: "l6", hint: "icon_item_pl_shoes_c01" }, { slot: "belt", area: "r6", hint: "icon_item_belt_c01" },
];

function Doll({ slots, items, selected, onSlot, canSwap, onSwap }: {
  slots: SavedBuild["sets"][number]["slots"]; items: Map<number, GearItem>; selected: SlotKey | null; onSlot(slot: SlotKey, filled: boolean): void;
  canSwap: boolean; onSwap(): void;
}) {
  const chosen = selected ? slots[selected] : undefined;
  const chosenItem = chosen ? items.get(chosen.id) : undefined;
  return (
    <section className="gear-doll" aria-label="Экипировка">
      <div className="gear-doll-grid">
        <button type="button" className="gear-swap" style={{ gridArea: "swap" }} disabled={!canSwap} onClick={onSwap} aria-label="Поменять оружие местами"
          title={canSwap ? "Поменять оружие в руках местами" : "Оружие не поменять: нужны два оружия для одной руки или одно, подходящее для обеих"}>
          <IconSwap />
        </button>
        {DOLL_LAYOUT.map(({ slot, area, hint }) => {
          const s = slots[slot];
          const item = s ? items.get(s.id) : undefined;
          return (
            <button key={slot} type="button" style={{ gridArea: area }} title={item ? `${SLOT_NAME[slot]}: ${item.name}` : SLOT_NAME[slot]}
              aria-label={item ? `${SLOT_NAME[slot]}: ${item.name}` : `${SLOT_NAME[slot]}: пусто`}
              className={`gear-cell-slot${selected === slot ? " sel" : ""}${item ? ` filled g-${item.grade}` : ""}`} onClick={() => onSlot(slot, !!item)}>
              {item ? <Icon name={item.icon} size={46} /> : <span className="hint"><Icon name={hint} size={46} /></span>}
              {item && s!.enchant > 0 && <em className="plus">+{s!.enchant}</em>}
              {item && s!.stones.some(Boolean) && <i className="dots">{s!.stones.map((x, i) => <b key={i} className={x ? "on" : ""} />)}</i>}
            </button>
          );
        })}
      </div>
      <div className="gear-doll-name">
        {chosenItem ? <><small>{SLOT_NAME[selected!]}</small><b className={`g-${chosenItem.grade}`}>{chosenItem.name}</b></>
          : <small>Нажми на слот: пустой откроет список вещей, занятый — заточку и камни.</small>}
      </div>
    </section>
  );
}

/** «Усиление»: the scrolls, the class's buffs and the ones other classes share, the title. */
function AmpPanel({ cls, level, set, titles, onChange }: {
  cls: string; level: number; set: SavedBuild["sets"][number]; titles: Title[];
  onChange(fn: (s: SavedBuild["sets"][number]) => SavedBuild["sets"][number]): void;
}) {
  const [titleQuery, setTitleQuery] = useState("");
  const buffs = set.buffs ?? [];
  const scrolls = set.scrolls ?? [];
  const toggleBuff = (id: number) => onChange((s) => ({ ...s, buffs: buffs.includes(id) ? buffs.filter((x) => x !== id) : [...buffs, id] }));
  const toggleScroll = (type: string) => onChange((s) => ({ ...s, scrolls: scrolls.includes(type) ? scrolls.filter((x) => x !== type) : [...scrolls, type] }));
  const own = (ACTIVE[cls] ?? []).map((skill) => ({ skill, step: buffAt(skill, level) })).filter((x) => x.step);
  const shared = Object.entries(ACTIVE).filter(([owner]) => owner !== cls).flatMap(([owner, list]) => list.filter((s) => s.share)
    .map((skill) => ({ owner, skill, step: buffAt(skill, level) }))).filter((x) => x.step);
  const ownerName = (id: string) => CLASSES.find(([c]) => c === id)?.[1] ?? id;
  const fold = (t: string) => t.toLowerCase().split("ё").join("е");
  const title = titles.find((t) => t.id === set.gearTitle);
  const titleList = titles.filter((t) => !titleQuery || fold(t.name).includes(fold(titleQuery))).slice(0, 60);
  return (
    <div className="gear-amp">
      <div className="gear-amp-group">
        <h5>Свитки</h5>
        <div className="gear-icons">
          {SCROLLS.map((x) => {
            const grade = scrollAt(x, level);
            if (!grade) return null;
            const on = scrolls.includes(x.type);
            return <button key={x.type} type="button" className={`gear-buff${on ? " on" : ""}`} aria-pressed={on} title={grade.name} onClick={() => toggleScroll(x.type)}>
              {grade.icon ? <Icon name={grade.icon} size={38} /> : <span className="icon blank" />}
            </button>;
          })}
        </div>
      </div>
      <div className="gear-amp-group">
        <h5>Умения класса</h5>
        <div className="gear-buffs">
          {own.length ? own.map(({ skill, step }) => <BuffRow key={skill.id} name={step!.name} icon={step!.icon} on={buffs.includes(skill.id)} onToggle={() => toggleBuff(skill.id)} />)
            : <p className="dbt-note">На этом уровне умений, меняющих характеристики, нет.</p>}
        </div>
      </div>
      <div className="gear-amp-group">
        <h5>Баффы других классов</h5>
        <div className="gear-buffs">
          {shared.map(({ owner, skill, step }) => <BuffRow key={`${owner}-${skill.id}`} name={step!.name} sub={ownerName(owner)} icon={step!.icon}
            on={buffs.includes(skill.id)} onToggle={() => toggleBuff(skill.id)} />)}
        </div>
      </div>
      <div className="gear-amp-group">
        <h5>Титул</h5>
        {title && <div className="gear-title-on"><b>{title.name}</b><span>{title.bonus.join(", ")}</span>
          <button type="button" className="btn" onClick={() => onChange((s) => ({ ...s, gearTitle: null }))}>Снять</button></div>}
        <div className="bst-search"><IconSearch /><input className="field" placeholder="Найти титул…" value={titleQuery} onChange={(e) => setTitleQuery(e.target.value)} aria-label="Поиск титула" /></div>
        <ul className="gear-titles">
          {titleList.map((t) => (
            <li key={t.id}><button type="button" className={t.id === set.gearTitle ? "on" : ""} onClick={() => onChange((s) => ({ ...s, gearTitle: t.id }))}>
              <b>{t.name}</b><span>{t.bonus.join(", ")}</span></button></li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function BuffRow({ name, sub, icon, on, onToggle }: { name: string; sub?: string; icon: string | null; on: boolean; onToggle(): void }) {
  return (
    <button type="button" className={`gear-buffrow${on ? " on" : ""}`} aria-pressed={on} onClick={onToggle}>
      {icon ? <Icon name={icon} size={32} /> : <span className="icon blank" />}
      <span><b>{name}</b>{sub && <small>{sub}</small>}</span>
      <i className="tick" aria-hidden />
    </button>
  );
}
