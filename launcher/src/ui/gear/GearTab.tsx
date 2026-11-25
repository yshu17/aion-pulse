// «Калькуляторы → Экипировка»: the gear calculator of Aion Classic 2.0 (docs/GEAR_CALC_PLAN.md), aiongear.fun's eu20 one
// in Pulse+'s look. Class and level, the doll, a picker per slot, the item's enchant and manastones, the characteristics,
// up to four gear sets and their comparison. The build is kept in this computer's storage.
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";

import classStats from "../../../../data/gear/eu20/class_stats.json";
import passiveTable from "../../../../data/gear/eu20/passive_skills.json";
import activeTable from "../../../../data/gear/eu20/active_skills.json";
import scrollTable from "../../../../data/gear/eu20/scrolls.json";
import { addSet, emptyBuild, KEY, MAX_SETS, readBuild, removeSet, withSet, writeBuild, type SavedBuild, type SavedSlot, stoneCap, subBlocked, swapWeapons, putItem } from "../../core/gear/build";
import { buffAt, calcStats, canEnchant, canStone, stoneSlots, display, passiveSkills, scrollAt, titleLines, type ActiveSkill, type BaseRow, type Equipped, type GearItem, type GearSet,
  type ScrollData, type SlotKey, type StatMap, type Stone } from "../../core/gear/engine";
import { CLASSES, PANEL, SLOT_NAME, groupName, statName } from "../../core/gear/labels";
import { gearChoices, gearGroups, gearItem, gearSets, gearStones, gearTitles } from "../../core/db/gear";
import { effectLines } from "../../core/gear/tips";
import { applySet, planSet, type SetPlan } from "../../core/gear/wearSet";
import { activeBuffs, buffKey, readBuffs, toggleBuff } from "../../core/gear/buffs";
import { chosenConsumables, consumableLines } from "../../core/gear/consumables";
import { CONSUMABLES, ConsumablesBox } from "./ConsumablesBox";
import { findTitles, titleSide, titleSummary, type GearTitle } from "../../core/gear/titles";
import { bonusLine } from "../../core/items/statNames";
import { useHoverTip, type TipInfo } from "./HoverTip";
import { RARITY } from "../../core/bestiary/card";
import type { All } from "../../core/db/npcPoints";
import { PickMenu } from "../bestiary/PickMenu";
import { useOpenRef } from "../map/placeLink";
import { CardBody, useSpec, hasStoneBlock, StoneUi } from "../ItemCard";
import { Icon } from "../Icon";
import { IconClose, IconReset, IconSearch, IconSwap } from "../icons";
import { m } from "motion/react";
import { EASE } from "../fx";
import { slotStones, withoutStones } from "../../core/gear/stones";
import type { Block } from "../../core/items/card";
import { StonePicker, StoneSquares } from "./StonePicker";
import { pulseDb } from "../db/pulseDb";
import "../bestiary/bestiary.css";
import "./gear.css";

const BASE = (classStats as { classes: Record<string, BaseRow[]> }).classes;
const PASSIVES = passiveTable as unknown as Parameters<typeof passiveSkills>[2];
const PASSIVE_ICONS: Record<string, string | undefined> = Object.fromEntries(Object.entries(PASSIVES.skills).map(([id, x]) => [id, x.icon as string | undefined]));
const ACTIVE = (activeTable as unknown as { classes: Record<string, ActiveSkill[]> }).classes;
const SCROLLS = (scrollTable as unknown as { scrolls: ScrollData[] }).scrolls;
const GRADES = ["mythic", "epic", "unique", "legend", "rare", "common"];
type Title = GearTitle;

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
      skills: [...passiveSkills(build.cls, build.level, PASSIVES), ...activeBuffs(readBuffs(set.buffs ?? [], build.cls, ACTIVE), build.cls, build.level, ACTIVE)],
      scrolls: (set.scrolls ?? []).map((type) => SCROLLS.find((x) => x.type === type)).filter((x): x is ScrollData => !!x)
        .map((x) => ({ effects: x.effects, times: scrollAt(x, build.level)?.level ?? 0 })).filter((x) => x.times > 0),
      title: title ? titleLines(title.bonus) : undefined,
      consumables: consumableLines(chosenConsumables(set.consumables, CONSUMABLES)),
    });
  }, [build, items, sets, stoneById, titles]);
  const stats = useMemo(() => statsOf(build.active), [statsOf, build.active]);
  const naked = useMemo(() => calcStats({ cls: build.cls, level: build.level, base: BASE[build.cls][build.level - 1], sets: [], slots: {},
    skills: passiveSkills(build.cls, build.level, PASSIVES) }), [build.cls, build.level]);

  const active = build.sets[build.active];
  const change = (fn: (s: SavedBuild["sets"][number]) => SavedBuild["sets"][number]) => setBuild((b) => withSet(b, b.active, fn));
  const put = (slot: SlotKey, item: GearItem) => {
    const known = new Map(items).set(item.id, item);
    const next = putItem(active.slots, slot, item, known);
    if (!next) { setPicking(null); return; } // the off hand is taken by a two-hander
    setItems(known);
    change((s) => ({ ...s, slots: next }));
    setSelected(slot);
    setPicking(null);
  };
  const swapHands = () => {
    const next = swapWeapons(active.slots, items);
    if (next) change((s) => ({ ...s, slots: next }));
  };
  const canSwap = !!swapWeapons(active.slots, items);
  // «Надеть комплект»: when a busy slot would lose its item, ask first (SetConfirm)
  const [pending, setPending] = useState<{ set: GearSet; plan: SetPlan } | null>(null);
  const wear = (plan: SetPlan, onlyFree = false) => {
    setItems((old) => { const next = new Map(old); for (const x of plan.puts) next.set(x.item.id, x.item); return next; });
    change((s) => ({ ...s, slots: applySet(s.slots, plan, onlyFree) }));
    setPending(null);
  };
  const wearSet = async (setId: number) => {
    if (!all) return;
    const [set] = await gearSets(all, [setId]);
    if (!set) return;
    const pieces = (await Promise.all(set.items.map((id) => gearItem(all, id)))).filter((x): x is GearItem => !!x);
    const plan = planSet(active.slots, pieces, items, build.cls);
    if (plan.removed.length) setPending({ set, plan });
    else wear(plan);
  };
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
        <Doll slots={active.slots} items={items} stoneById={stoneById} selected={selected} onSlot={(slot, filled) => (filled ? setSelected(slot) : setPicking(slot))} onTakeOff={(slot) => { takeOff(slot); setSelected((cur) => (cur === slot ? null : cur)); }} subBlocked={subBlocked(active.slots, items)}
          canSwap={canSwap} onSwap={() => { swapHands(); setSelected((s) => (s === "main" ? "sub" : s === "sub" ? "main" : s)); }} />

        <section className="gear-item" aria-label="Предмет">
          {all === null && <div className="bst-empty">База игры не найдена: нет файла data/pulse.db.</div>}
          {selected && chosen && chosenItem ? <SlotPanel slot={selected} item={chosenItem} saved={chosen} stones={stones}
            onEnchant={(n) => setSlot(selected, (x) => ({ ...x, enchant: n }))}
            onStone={(i, id) => setSlot(selected, (x) => { const st = [...x.stones]; st[i] = id; return { ...x, stones: st }; })}
            onReplace={() => setPicking(selected)} onTakeOff={() => { takeOff(selected); setSelected(null); }} />
            : <div className="bst-empty">Выбери слот: пустой откроет список вещей, занятый — заточку и камни.</div>}
          {sets.length > 0 && <SetsPanel sets={sets} slots={equipped(active.slots, items, stoneById)} all={all ?? null} onWear={wearSet} />}
        </section>

        <section className="gear-stats" aria-label="Характеристики">
          <div className="gear-tabs">
            <button type="button" className={view === "stats" ? "on" : ""} onClick={() => setView("stats")}>Характеристики</button>
            <button type="button" className={view === "amp" ? "on" : ""} onClick={() => setView("amp")}>Усиление</button>
            <button type="button" className={view === "compare" ? "on" : ""} onClick={() => setView("compare")} disabled={build.sets.length < 2}>Сравнение наборов</button>
          </div>
          {view === "amp" ? <AmpPanel cls={build.cls} level={build.level} set={active} titles={titles} all={all ?? null} onChange={change} />
            : view === "stats" || build.sets.length < 2 ? <StatsPanel stats={stats} naked={naked} /> : <ComparePanel build={build} statsOf={statsOf} />}
        </section>
      </div>

      {picking && all && <Picker all={all} slot={picking} cls={build.cls} level={build.level} onPick={(item) => put(picking, item)} onClose={() => setPicking(null)}
        onSet={(id) => { setPicking(null); wearSet(id); }} />}
      {pending && <SetConfirm set={pending.set} plan={pending.plan} items={items} onAll={() => wear(pending.plan)} onFree={() => wear(pending.plan, true)} onClose={() => setPending(null)} />}
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
  const spec = useSpec(String(item.id));
  const open = useOpenRef();
  // an item that takes no manastones shows none of the card's lines and empty squares about them
  const answer = useMemo(() => (spec?.spec && !canStone(item) ? { ...spec, spec: { ...spec.spec, blocks: withoutStones(spec.spec.blocks as Block[]) } } : spec), [spec, item]);
  // the card says how high a stone the item takes («70-го уровня и ниже»); without that line, ten levels above the item
  const cap = stoneCap(answer?.spec?.blocks as { kind?: string; text?: string }[] | undefined) ?? Math.min(item.level + 10, 70);
  const fits = stones.filter((s) => s.level <= cap);
  const slots = stoneSlots(item);
  const optional = slots > 0 ? item.stonesBonus ?? 0 : 0;
  // the stones are drawn in the card, in place of its empty squares; a card without them gets the picker above it
  const inCard = hasStoneBlock(answer?.spec?.blocks as Block[] | undefined);
  const stoneById = new Map(fits.map((x) => [x.id, x]));
  const chosen = Array.from({ length: slots }, (_, i) => saved.stones[i] ?? null);
  const picker = <StonePicker slots={slots} optional={optional} chosen={chosen} fits={fits} onStone={onStone} />;
  const { adds } = slotStones(item, saved, stoneById);
  return (
    <m.div className="gear-slotpanel" key={item.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, ease: EASE }}>
      <div className="gear-slotpanel-head">
        <span className="dbt-made-title">{SLOT_NAME[slot]} · {groupName(item.grp)}</span>
        <span className="spacer" />
        {open && <button type="button" className="btn" onClick={() => open({ kind: "item", id: String(item.id), name: item.name })}>Показать в БД</button>}
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
          </> : <em>не точится</em>}
        </div>
        {slots === 0 && <div className="gear-enchant"><span>Камни</span>
          <em>{!canStone(item) ? "не вставляются" : item.stones === null ? "слоты не известны" : "нет слотов"}</em></div>}
        {slots > 0 && answer && !inCard && picker}
      </div>
      <StoneUi.Provider value={{ ui: slots > 0 && inCard ? picker : null, adds }}>
        <CardBody id={String(item.id)} answer={answer} className="in-db" fallback={{ name: item.name, icon: item.icon, grade: item.grade, level: item.level, kind: groupName(item.grp) }} />
      </StoneUi.Provider>
    </m.div>
  );
}

function SetsPanel({ sets, slots, all, onWear }: { sets: GearSet[]; slots: Partial<Record<SlotKey, Equipped>>; all: All | null; onWear(setId: number): void }) {
  const worn = new Set(Object.values(slots).map((e) => e!.item.id));
  const shown = sets.filter((s) => s.items.some((id) => worn.has(id)));
  if (!shown.length) return null;
  return (
    <div className="gear-setinfo">
      {shown.map((set) => <SetBox key={set.id} set={set} worn={worn} all={all} onWear={() => onWear(set.id)} />)}
    </div>
  );
}

/** A set of the worn items: its pieces (worn ones lit), the bonuses lit as they are reached, and «Надеть комплект». */
function SetBox({ set, worn, all, onWear }: { set: GearSet; worn: Set<number>; all: All | null; onWear(): void }) {
  const [pieces, setPieces] = useState<GearItem[]>([]);
  const tip = useHoverTip(null);
  useEffect(() => {
    let alive = true;
    if (all) Promise.all(set.items.map((id) => gearItem(all, id))).then((got) => alive && setPieces(got.filter((x): x is GearItem => !!x)));
    return () => { alive = false; };
  }, [all, set]);
  const n = set.items.filter((id) => worn.has(id)).length;
  const left = set.items.length - n;
  return (
    <div className="dbt-box">
      <div className="gear-set-head">
        <h5>{set.name} · {n} из {set.items.length}</h5>
        {left > 0 && <button type="button" className="btn primary" onClick={onWear}>Надеть комплект: ещё {left}</button>}
      </div>
      {pieces.length > 0 && <div className="gear-set-items">
        {pieces.map((i) => <span key={i.id} tabIndex={0} className={`gear-set-piece${worn.has(i.id) ? ` on g-${i.grade}` : ""}`}
          aria-label={`${i.name}: ${worn.has(i.id) ? "надета" : "не надета"}`} {...tip.bind(itemTip(i, worn.has(i.id) ? "Надета" : "Не надета"))}>
          <Icon name={i.icon} size={34} /></span>)}
      </div>}
      {set.bonuses.map((b, i) => {
        const on = b.need === 0 ? n >= set.items.length : n >= b.need;
        return <p key={i} className={`gear-setline${on ? " on" : ""}`}>{b.need === 0 ? "Полный набор" : `${b.need} предм.`}: {b.stats.map(([s, v, p]) => `${statName(s)} +${v}${p ? "%" : ""}`).join(", ")}</p>;
      })}
      {tip.box}
    </div>
  );
}

/** What a set would take off, asked before it is worn. */
function SetConfirm({ set, plan, items, onAll, onFree, onClose }: {
  set: GearSet; plan: SetPlan; items: Map<number, GearItem>; onAll(): void; onFree(): void; onClose(): void;
}) {
  useEffect(() => { const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", esc); return () => window.removeEventListener("keydown", esc); }, [onClose]);
  const free = plan.puts.some((x) => !x.takes.length);
  return (
    <div className="gear-modal" role="alertdialog" aria-label={`Надеть ${set.name}`} onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="gear-confirm">
        <b>Надеть «{set.name}»? Будет снято:</b>
        <ul>{plan.removed.map((r) => <li key={r.slot}>{SLOT_NAME[r.slot]}: <span>{items.get(r.id)?.name ?? `ID ${r.id}`}</span></li>)}</ul>
        {plan.cannot.length > 0 && <p className="dbt-note">Класс не может надеть: {plan.cannot.map((i) => i.name).join(", ")}.</p>}
        <div>
          <button type="button" className="btn primary" autoFocus onClick={onAll}>Надеть и снять</button>
          {free && <button type="button" className="btn" onClick={onFree}>Только в свободные</button>}
          <button type="button" className="btn" onClick={onClose}>Отмена</button>
        </div>
      </div>
    </div>
  );
}

/** The list of what fits a slot, with the filters of the site: type, level, grade, name. */
function Picker({ all, slot, cls, level, onPick, onClose, onSet }: { all: All; slot: SlotKey; cls: string; level: number; onPick(item: GearItem): void; onClose(): void; onSet(setId: number): void }) {
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
  const tip = useHoverTip(null);
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
                <button type="button" onClick={() => onPick(i)} {...tip.bind(itemTip(i, SLOT_NAME[slot]))}>
                  <span className="lvl">{i.level}</span>
                  <Icon name={i.icon} size={32} />
                  <span className={`nm g-${i.grade}`}>{i.name}</span>
                  <span className="grp">{groupName(i.grp)}</span>
                  <span className="sum">{summary(i)}</span>
                </button>
                {i.setId !== null && <button type="button" className="gear-setchip" onClick={() => onSet(i.setId!)} title="Надеть весь комплект этой вещи"
                  aria-label={`Надеть комплект: ${i.name}`}>Комплект</button>}
              </li>
            ))}
        </ul>
      </div>
      {tip.box}
    </div>
  );
}

/** An item's tooltip: the card «База данных» shows for it (HoverTip). */
const itemTip = (i: GearItem, kind: string): TipInfo =>
  ({ name: i.name, kind, icon: i.icon, lines: [], item: { id: String(i.id), icon: i.icon, grade: i.grade, level: i.level, kind: groupName(i.grp) } });

/** A slot's tooltip: the item's card with the stones put into its squares and the numbers they and the enchant add. */
function slotTip(item: GearItem, saved: SavedSlot, stoneById: Map<number, Stone>, kind: string): TipInfo {
  const { worn, optional, adds } = slotStones(item, saved, stoneById);
  return { ...itemTip(item, kind), stones: { ui: worn.length ? <StoneSquares worn={worn} optional={optional} /> : null, adds } };
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

function Doll({ slots, items, stoneById, selected, onSlot, onTakeOff, canSwap, onSwap, subBlocked }: {
  slots: SavedBuild["sets"][number]["slots"]; items: Map<number, GearItem>; stoneById: Map<number, Stone>; selected: SlotKey | null; onSlot(slot: SlotKey, filled: boolean): void; onTakeOff(slot: SlotKey): void;
  canSwap: boolean; onSwap(): void; subBlocked: boolean;
}) {
  const chosen = selected ? slots[selected] : undefined;
  const chosenItem = chosen ? items.get(chosen.id) : undefined;
  const tip = useHoverTip(null);
  return (
    <section className="gear-doll" aria-label="Экипировка">
      {tip.box}
      <div className="gear-doll-grid">
        <button type="button" className="gear-swap" style={{ gridArea: "swap" }} disabled={!canSwap} onClick={onSwap} aria-label="Поменять оружие местами"
          title={canSwap ? "Поменять оружие в руках местами" : "Оружие не поменять: нужны два оружия для одной руки или одно, подходящее для обеих"}>
          <IconSwap />
        </button>
        {DOLL_LAYOUT.map(({ slot, area, hint }) => {
          const s = slots[slot];
          const blocked = slot === "sub" && subBlocked;
          const item = s && !blocked ? items.get(s.id) : undefined;
          return (
            <div key={slot} className="gear-cell-wrap" style={{ gridArea: area }}>
              <button type="button" disabled={blocked} {...(item ? tip.bind(slotTip(item, s!, stoneById, SLOT_NAME[slot])) : {})}
                title={blocked ? "Левая рука занята двуручным оружием" : item ? undefined : SLOT_NAME[slot]}
                aria-label={item ? `${SLOT_NAME[slot]}: ${item.name}` : `${SLOT_NAME[slot]}: пусто`}
                className={`gear-cell-slot${selected === slot ? " sel" : ""}${item ? ` filled g-${item.grade}` : ""}`} onClick={() => onSlot(slot, !!item)}>
                {item ? <Icon name={item.icon} size={46} /> : <span className="hint"><Icon name={hint} size={46} /></span>}
                {item && s!.enchant > 0 && <em className="plus">+{s!.enchant}</em>}
                {item && canStone(item) && s!.stones.some(Boolean) && <i className="dots">{s!.stones.map((x, i) => <b key={i} className={x ? "on" : ""} />)}</i>}
              </button>
              {item && <button type="button" className="gear-cell-x" aria-label={`Снять: ${item.name}`} title={`Снять: ${item.name}`} onClick={() => onTakeOff(slot)}><IconClose /></button>}
            </div>
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

/** «Усиление», as the site has it: the class's skills and the other classes' buffs as grids of pictures (the name and
 * what it does are in the tooltip), the passives on demand, the scrolls, the food and drinks, the title. */
function AmpPanel({ cls, level, set, titles, all, onChange }: {
  cls: string; level: number; set: SavedBuild["sets"][number]; titles: Title[]; all: All | null;
  onChange(fn: (s: SavedBuild["sets"][number]) => SavedBuild["sets"][number]): void;
}) {
  const tip = useHoverTip(all);
  const [passives, setPassives] = useState(false);
  const buffs = readBuffs(set.buffs ?? [], cls, ACTIVE);
  const scrolls = set.scrolls ?? [];
  const toggle = (key: string) => onChange((s) => ({ ...s, buffs: toggleBuff(buffs, key) }));
  const toggleScroll = (type: string) => onChange((s) => ({ ...s, scrolls: scrolls.includes(type) ? scrolls.filter((x) => x !== type) : [...scrolls, type] }));
  const own = (ACTIVE[cls] ?? []).map((skill) => ({ skill, step: buffAt(skill, level) })).filter((x) => x.step);
  const shared = Object.entries(ACTIVE).filter(([owner]) => owner !== cls).flatMap(([owner, list]) => list.filter((s) => s.share)
    .map((skill) => ({ owner, skill, step: buffAt(skill, level) }))).filter((x) => x.step);
  const ownerName = (id: string) => CLASSES.find(([c]) => c === id)?.[1] ?? id;
  const passive = passiveSkills(cls, level, PASSIVES).map((x) => ({ ...x, icon: PASSIVE_ICONS[String(x.id)] }));
  const chosen = own.filter((x) => buffs.includes(buffKey(cls, x.skill.id))).length + shared.filter((x) => buffs.includes(buffKey(x.owner, x.skill.id))).length;
  return (
    <div className="gear-amp">
      <div className="gear-amp-group">
        <h5>Умения <span>выбрано {chosen}</span><i className="spacer" />
          <button type="button" className="btn" aria-pressed={passives} onClick={() => setPassives((v) => !v)}>{passives ? "Скрыть пассивные" : "Показать пассивные"}</button>
          <button type="button" className="btn" disabled={!buffs.length && !scrolls.length && !chosenConsumables(set.consumables, CONSUMABLES).length}
            title="Выключить умения, баффы, свитки и расходники" onClick={() => onChange((s) => ({ ...s, buffs: [], scrolls: [], consumables: {} }))}><IconReset />Сбросить</button>
        </h5>
        {own.length ? <div className="gear-icons" aria-label="Умения класса">
          {own.map(({ skill, step }) => <BuffIcon key={skill.id} name={step!.name} icon={step!.icon} on={buffs.includes(buffKey(cls, skill.id))} onToggle={() => toggle(buffKey(cls, skill.id))}
            tip={tip.bind({ name: step!.name, kind: "Умение класса", icon: step!.icon, lines: effectLines(step!.effects, true) })} />)}
        </div> : <p className="dbt-note">На этом уровне умений, меняющих характеристики, нет.</p>}
        {passives && <div className="gear-icons gear-icons-sep" aria-label="Пассивные умения">
          {passive.map((x) => <span key={x.id} className="gear-buff passive" tabIndex={0} aria-label="Пассивное умение: считается всегда"
            {...tip.bind({ name: "Пассивное умение", kind: "Считается всегда", icon: x.icon ? `skills/${x.icon}` : null, lines: effectLines(x.effects) })}>
            {x.icon ? <Icon name={`skills/${x.icon}`} size={34} /> : <span className="icon blank" />}</span>)}
        </div>}
        {shared.length > 0 && <div className="gear-icons gear-icons-sep" aria-label="Баффы других классов">
          {shared.map(({ owner, skill, step }) => <BuffIcon key={`${owner}-${skill.id}`} name={`${step!.name} (${ownerName(owner)})`} icon={step!.icon} badge={ownerName(owner)[0]}
            on={buffs.includes(buffKey(owner, skill.id))} onToggle={() => toggle(buffKey(owner, skill.id))}
            tip={tip.bind({ name: step!.name, kind: `Бафф: ${ownerName(owner)}`, icon: step!.icon, lines: effectLines(step!.effects, true) })} />)}
        </div>}
        <p className="dbt-note">Сверху умения класса, ниже баффы других классов: буква в углу — чей это бафф.</p>
      </div>
      <div className="gear-amp-group">
        <h5>Свитки</h5>
        <div className="gear-icons">
          {SCROLLS.map((x) => {
            const grade = scrollAt(x, level);
            if (!grade) return null;
            return <BuffIcon key={x.type} name={grade.name} icon={grade.icon} on={scrolls.includes(x.type)} onToggle={() => toggleScroll(x.type)}
              tip={tip.bind({ name: grade.name, kind: "Свиток", icon: grade.icon, lines: effectLines(x.effects, true), byName: true })} />;
          })}
        </div>
      </div>
      <ConsumablesBox saved={set.consumables} all={all} onChange={(consumables) => onChange((s) => ({ ...s, consumables }))} />
      <TitlePick titles={titles} picked={set.gearTitle ?? null} onPick={(id) => onChange((s) => ({ ...s, gearTitle: id }))} />
      {tip.box}
    </div>
  );
}

function BuffIcon({ name, icon, badge, on, onToggle, tip }: { name: string; icon: string | null; badge?: string; on: boolean; onToggle(): void; tip?: object }) {
  return (
    <button type="button" className={`gear-buff${on ? " on" : ""}`} aria-pressed={on} aria-label={name} onClick={onToggle} {...tip}>
      {icon ? <Icon name={icon} size={34} /> : <span className="icon blank" />}
      {badge && <em aria-hidden>{badge}</em>}
    </button>
  );
}

/** «Титул»: the chosen one as «База данных» shows it, with «Сменить» and «Снять»; the search and the list only while choosing. */
function TitlePick({ titles, picked, onPick }: { titles: Title[]; picked: number | null; onPick(id: number | null): void }) {
  const [changing, setChanging] = useState(false);
  const [query, setQuery] = useState("");
  const change = useRef<HTMLButtonElement>(null);
  const focusChange = useRef(false);
  useEffect(() => { if (focusChange.current && change.current) { focusChange.current = false; change.current.focus(); } });
  const title = titles.find((t) => t.id === picked);
  const listing = !title || changing;
  const found = listing ? findTitles(titles, query) : [];
  const close = () => { setChanging(false); setQuery(""); focusChange.current = true; };
  return (
    <div className="gear-amp-group" onKeyDown={(e) => { if (e.key === "Escape" && changing) { e.stopPropagation(); close(); } }}>
      <h5>Титул</h5>
      {!listing && title ? (
        <div className="gear-title-card">
          {title.icon ? <Icon name={title.icon} size={40} /> : <span className="icon blank" />}
          <div>
            <b>{title.name}</b><span>{titleSide(title.race)}</span>
            <dl>{title.bonus.map((b) => { const [k, v] = bonusLine(b); return <Fragment key={b}><dt>{k}</dt><dd>{v}</dd></Fragment>; })}</dl>
          </div>
          <div className="gear-title-acts">
            <button type="button" className="btn primary" ref={change} onClick={() => setChanging(true)}>Сменить</button>
            <button type="button" className="btn" onClick={() => { onPick(null); setChanging(false); }}>Снять</button>
          </div>
        </div>
      ) : (
        <>
          <div className="bst-search"><IconSearch /><input className="field" autoFocus={changing} placeholder="Найти титул по названию или бонусу…" value={query}
            onChange={(e) => setQuery(e.target.value)} aria-label="Поиск титула" /></div>
          <ul className="gear-titles">
            {found.map((t) => (
              <li key={t.id}><button type="button" className={t.id === picked ? "on" : ""} onClick={() => { onPick(t.id); close(); }}>
                {t.icon ? <Icon name={t.icon} size={32} /> : <span className="icon blank" />}
                <span><b>{t.name}</b><small>{[titleSide(t.race), titleSummary(t.bonus)].filter(Boolean).join(" · ")}</small></span>
              </button></li>
            ))}
            {!found.length && <li className="dbt-note">Ничего не нашлось. Попробуй часть названия или бонус, например «крит».</li>}
          </ul>
          {changing && <button type="button" className="btn" onClick={close}>Отмена</button>}
        </>
      )}
    </div>
  );
}
