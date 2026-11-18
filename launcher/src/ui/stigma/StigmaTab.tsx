// «Калькуляторы → Стигмы»: the stigma calculator of github.com/Persepha/Aion-classic-stigma-calculator in Pulse+'s look.
// Class, faction and level; the game's stigma window (six normal and five advanced slots, the client's own frames); the
// class's stigmas and the two advanced trees with their arrows; the card of the chosen stigma. A stigma goes into the window
// by drag and drop, a click shows its card, the pointer over it shows a short note (name, price, shards, abyss points).
// The calculator's data come first (data/stigma/classic24.json), pulse.db second (Russian names and texts, icons, stones,
// prices, the client's dependencies and the stigmas only the client has): core/stigma/merge.ts.
import { memo, useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type FocusEvent as ReactFocusEvent, type MouseEvent as ReactMouseEvent } from "react";
import { AnimatePresence, m } from "motion/react";

import calcData from "../../../../data/stigma/classic24.json";
import { add, bestLevel, canAdd, cost, dependantsOf, emptyPick, levelOf, MAX_LEVEL, MIN_LEVEL, needsOf, picked, refit, remove, SLOT_LEVELS, slotsAt,
  type Ctx, type Faction, type Pick, type Stigma, type StigmaLevel } from "../../core/stigma/calc";
import { classStigmas, PLACES, treeEdges, type CalcData } from "../../core/stigma/data";
import { clientStigmas, mergeNeeds, mergeStigmas, readDb, type DbSkill, type DbStone, type GitStigma } from "../../core/stigma/merge";
import { castText, cooldownText, infoText, kindText, targetText } from "../../core/stigma/labels";
import { KEY, readSaved, writeSaved, type Saved } from "../../core/stigma/save";
import { CLASSES } from "../../core/gear/labels";
import type { All } from "../../core/db/npcPoints";
import { PickMenu } from "../bestiary/PickMenu";
import { Icon } from "../Icon";
import { IconClose, IconReset } from "../icons";
import { EASE, Glide, Pop, row } from "../fx";
import { useOpenRef } from "../map/placeLink";
import { SkillText } from "../SkillText";
import { pulseDb } from "../db/pulseDb";
import "../bestiary/bestiary.css";
import "./stigma.css";

const DATA = calcData as unknown as CalcData;
const ALL_GIT = Object.values(DATA.classes).flatMap((c) => c.stigmas);
const ALL_SKILLS = [...new Set(ALL_GIT.flatMap((s) => s.levels.map((l) => l.skill)))];
const FACTIONS: [Faction, string][] = [["elyos", "Элийцы"], ["asmodian", "Асмодиане"]];
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"];
const SHARD_ICON = "icon_item_crystal"; // the client's «Осколок стигмы» (item 141000001)
const fmt = (n: number) => n.toLocaleString("ru-RU");

// the stigma window's pictures, cut from the client's UI atlas (tools/import_stigma_ui.py)
const UI = import.meta.glob("../../../../data/ui/stigma/*.png", { query: "?url", import: "default", eager: true }) as Record<string, string>;
const ui = (name: string) => UI[`../../../../data/ui/stigma/${name}.png`];

function load(): Saved {
  try { return readSaved(localStorage.getItem(KEY)); } catch { return readSaved(null); }
}

/** What a stigma's square says: picked, can be taken, too high for the character, or no room for it and its needs. */
type State = "on" | "ok" | "lock" | "full";
const stateOf = (ctx: Ctx, pick: Pick, s: Stigma): State =>
  picked(pick, s.id) ? "on" : bestLevel(s, ctx.level) === null ? "lock" : canAdd(ctx, pick, s.id) ? "ok" : "full";

/** The note under the pointer: which stigma, and where its square is. */
interface Tip { id: string; x: number; y: number; left: boolean }
/** What the squares and slots share: the chosen stigma, the note, the drag. */
interface Hands {
  focus: string | null;
  select(id: string): void;
  tip(id: string, target: HTMLElement): void;
  untip(): void;
  drag(id: string | null): void;
}
const DRAG = "application/x-pulse-stigma";

export function StigmaTab() {
  const [all, setAll] = useState<All | null | undefined>(undefined);
  const [db, setDb] = useState<{ skills: DbSkill[]; stones: DbStone[] } | null>(null);
  const [saved, setSaved] = useState<Saved>(load);
  const [focus, setFocus] = useState<string | null>(null);
  const [tip, setTip] = useState<Tip | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [say, setSay] = useState<string | null>(null);
  const tipTimer = useRef<number | undefined>(undefined);

  useEffect(() => { pulseDb().then((x) => setAll(() => x)).catch(() => setAll(null)); }, []);
  // an older database (before schema 10) lacks the stones' columns: the calculator's data alone then
  useEffect(() => { if (all) readDb(all, ALL_SKILLS).then(setDb).catch(() => setDb(null)); }, [all]);
  useEffect(() => { try { localStorage.setItem(KEY, writeSaved(saved)); } catch { /* storage closed: the build lives for this run */ } }, [saved]);
  useEffect(() => { if (!say) return; const t = window.setTimeout(() => setSay(null), 2600); return () => window.clearTimeout(t); }, [say]);
  useEffect(() => () => window.clearTimeout(tipTimer.current), []);

  const { cls, faction, level } = saved;
  const view = useMemo(() => {
    const raw = classStigmas(DATA, cls, faction);
    const git: Stigma[] = db ? mergeStigmas(raw.stigmas, db.skills, db.stones) : raw.stigmas.map((s) => ({ ...s, levels: s.levels.map((l) => ({ ...l })) }));
    const extra = db ? clientStigmas(cls, faction, ALL_GIT, db.skills, db.stones) : [];
    const needs = db ? mergeNeeds([...raw.stigmas, ...extra as GitStigma[]], raw.needs, db.skills, db.stones) : raw.needs;
    const stigmas = [...git, ...extra];
    return { stigmas, trees: raw.trees, needs, byId: new Map(stigmas.map((s) => [s.id, s])) };
  }, [cls, faction, db]);
  const ctx: Ctx = useMemo(() => ({ stigmas: view.byId, needs: view.needs, level }), [view, level]);
  // the kept pick checked against today's data (a new database can change a stigma's needs)
  const pick = useMemo(() => refit(ctx, saved.pick), [ctx, saved.pick]);
  const price = cost(ctx, pick);

  const setPick = useCallback((fn: (p: Pick) => Pick) => setSaved((s) => ({ ...s, pick: fn(refit(ctx, s.pick)) })), [ctx]);
  const take = useCallback((id: string) => {
    const s = ctx.stigmas.get(id);
    if (!s) return;
    const state = stateOf(ctx, pick, s);
    if (state === "ok") { setFocus(id); setPick((p) => add(ctx, p, id)); }
    else if (state === "lock") setSay(`«${levelLine(s, null).name}» — с ${s.levels[0].level} уровня, а у персонажа ${ctx.level}.`);
    else if (state === "full") setSay(`Для «${levelLine(s, null).name}» и нужных ей стигм не хватает слотов.`);
  }, [ctx, pick, setPick]);
  const drop = useCallback((id: string) => setPick((p) => remove(ctx, p, id)), [ctx, setPick]);
  const setLevel = (n: number) => {
    const next = Math.min(Math.max(Math.round(n) || MIN_LEVEL, MIN_LEVEL), MAX_LEVEL);
    setSaved((s) => ({ ...s, level: next, pick: refit({ ...ctx, level: next }, s.pick) }));
  };

  const hands: Hands = useMemo(() => ({
    focus,
    select: (id) => { setFocus(id); setTip(null); },
    tip: (id, target) => {
      window.clearTimeout(tipTimer.current);
      const r = target.getBoundingClientRect();
      const left = r.right + 300 > window.innerWidth;
      tipTimer.current = window.setTimeout(() => setTip({ id, x: left ? r.left - 8 : r.right + 8, y: r.top, left }), 120);
    },
    untip: () => { window.clearTimeout(tipTimer.current); setTip(null); },
    drag: (id) => { window.clearTimeout(tipTimer.current); setTip(null); setDragging(id); },
  }), [focus]);

  // «Только в клиенте» switch: on — the stigmas that pulse.db adds to the calculator's list show too; off — they are hidden
  const [showClient, setShowClient] = useState(false);
  const normal = view.stigmas.filter((s) => !s.advanced && (showClient || !s.onlyClient));
  const loose = view.stigmas.filter((s) => s.advanced && !view.trees.some((t) => t.includes(s.id)) && (showClient || !s.onlyClient));
  const shown = focus ? view.byId.get(focus) ?? null : null;
  const tipped = tip ? view.byId.get(tip.id) ?? null : null;
  const fromSlot = (e: DragEvent) => e.dataTransfer.types.includes(`${DRAG}-slot`);

  return (
    <main className="stg">
      <div className="bst-bar stg-bar">
        <PickMenu id="stg-class" label="Класс" text={CLASSES.find(([id]) => id === cls)?.[1] ?? "Класс"} value={cls}
          onPick={(c) => { setFocus(null); setSaved((s) => ({ ...s, cls: c, pick: emptyPick() })); }}
          options={CLASSES.map(([id, name]): [string, string] => [name, id])} />
        <div className="segmented" role="radiogroup" aria-label="Раса">
          {FACTIONS.map(([value, label]) => (
            <button key={value} type="button" role="radio" aria-checked={faction === value} className={faction === value ? "on" : ""}
              onClick={() => { setFocus(null); setSaved((s) => ({ ...s, faction: value, pick: emptyPick() })); }}>
              {faction === value && <Glide group="stg-faction" />}<span>{label}</span></button>
          ))}
        </div>
        <div className="stg-level" role="group" aria-label="Уровень персонажа">
          <span>Уровень</span>
          <button type="button" className="btn" onClick={() => setLevel(level - 1)} disabled={level <= MIN_LEVEL} aria-label="Ниже">−</button>
          <input type="number" min={MIN_LEVEL} max={MAX_LEVEL} value={level} aria-label="Уровень" onChange={(e) => setLevel(Number(e.target.value))} />
          <button type="button" className="btn" onClick={() => setLevel(level + 1)} disabled={level >= MAX_LEVEL} aria-label="Выше">+</button>
        </div>
        <span className="spacer" />
        <label className="check stg-only" title="Показать только стигмы, которых нет в калькуляторе, а есть в клиенте">
          <input type="checkbox" checked={showClient} onChange={(e) => setShowClient(e.target.checked)} />
          <span className="box" /><span>Только в клиенте</span><em className="stg-only-n">{view.stigmas.filter((s) => s.onlyClient).length}</em>
        </label>
        <button type="button" className="btn" onClick={() => setPick(() => emptyPick())} disabled={!pick.normal.length && !pick.advanced.length}>
          <IconReset /> Снять все</button>
      </div>

      {all === null && <div className="stg-note">Нет базы игры (data/pulse.db): названия и описания на английском, без значков.</div>}

      <div className="stg-body">
        <section className={`stg-panel stg-window${dragging && !dragging.startsWith("slot:") ? " dropping" : ""}`} aria-label="Окно стигм"
          onDragOver={(e) => { if (e.dataTransfer.types.includes(DRAG) && !fromSlot(e)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; } }}
          onDrop={(e) => { const id = e.dataTransfer.getData(DRAG); if (id && !fromSlot(e)) { e.preventDefault(); take(id); } setDragging(null); }}>
          <div className="stg-win">
            <Slots kind="normal" ids={pick.normal} ctx={ctx} pick={pick} hands={hands} onDrop={drop} />
            <Slots kind="advanced" ids={pick.advanced} ctx={ctx} pick={pick} hands={hands} onDrop={drop} />
          </div>
          <div className="stg-win-cost" aria-label="Цена набора">
            <span title="Осколки стигм"><Icon name={SHARD_ICON} size={18} /><Pop value={`${price.unknown ? "≈ " : ""}${fmt(price.shards)}`} /></span>
            <span title="Очки Бездны"><img src={ui("ap")} alt="" width={18} height={18} /><Pop value={fmt(price.ap)} /></span>
          </div>
          <AnimatePresence>{say && <m.p className="stg-say" role="status" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>{say}</m.p>}</AnimatePresence>
          <p className="stg-hint">Перетащи стигму в окно: нужные ей встанут сами. Обычная стигма займёт свободный продвинутый слот, если обычные заполнены. Чтобы снять, вытащи её из окна или нажми ×.</p>
        </section>

        <section className="stg-panel stg-pool" aria-label="Стигмы класса"
          onDragOver={(e) => { if (fromSlot(e)) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; } }}
          onDrop={(e) => { const id = e.dataTransfer.getData(`${DRAG}-slot`); if (id) { e.preventDefault(); drop(id); } setDragging(null); }}>
          <h4>Обычные стигмы</h4>
          <div className="stg-grid">
            {normal.map((s, i) => <Square key={s.id} s={s} state={stateOf(ctx, pick, s)} level={pickLevel(ctx, pick, s)} index={i} hands={hands} onTake={take} />)}
          </div>
          <h4>Продвинутые стигмы</h4>
          <div className="stg-trees">
            {view.trees.map((tree, t) => <Tree key={`${cls}-${faction}-${t}`} tree={tree} ctx={ctx} pick={pick} hands={hands} onTake={take} />)}
          </div>
          {loose.length > 0 && <>
            <h4>Продвинутые вне деревьев <em>есть только в клиенте</em></h4>
            <div className="stg-grid">
              {loose.map((s, i) => <Square key={s.id} s={s} state={stateOf(ctx, pick, s)} level={pickLevel(ctx, pick, s)} index={i} hands={hands} onTake={take} />)}
            </div>
          </>}
        </section>

        <section className="stg-panel stg-card" aria-label="Стигма" aria-live="polite">
          <AnimatePresence mode="wait">
            {shown ? <Card key={shown.id} s={shown} ctx={ctx} pick={pick} onTake={take} onDrop={drop} onSelect={hands.select}
              onLevel={(lv) => setSaved((x) => ({ ...x, pick: { ...pick, levels: { ...pick.levels, [shown.id]: lv } } }))} />
              : <m.div key="none" className="bst-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                Щёлкни по стигме, чтобы увидеть её описание. Чтобы взять стигму, перетащи её в окно стигм.</m.div>}
          </AnimatePresence>
          <p className="stg-source">Данные: <span>калькулятор Persepha (Aion Classic 2.4)</span>; названия, описания, цены, значки, связи и стигмы, которых нет в калькуляторе, из клиента игры.</p>
        </section>
      </div>

      <AnimatePresence>{tip && tipped && !dragging && <TipBox key={tip.id} tip={tip} s={tipped} ctx={ctx} pick={pick} />}</AnimatePresence>
    </main>
  );
}

/** The level a square shows: the chosen one of a picked stigma, else the highest the character wears. */
const pickLevel = (ctx: Ctx, pick: Pick, s: Stigma) => (picked(pick, s.id) ? pick.levels[s.id] : bestLevel(s, ctx.level)) ?? null;
const levelLine = (s: Stigma, level: number | null): StigmaLevel => s.levels.find((l) => l.level === level) ?? s.levels[s.levels.length - 1];
const roman = (s: Stigma, level: number | null) => ROMAN[Math.max(0, s.levels.findIndex((l) => l.level === level))] ?? "";

/** The pointer's events of a square or a slot: the note on hover, the card on click, a drag that hides the note. */
function pointer(hands: Hands, id: string) {
  return {
    onMouseEnter: (e: ReactMouseEvent<HTMLElement>) => hands.tip(id, e.currentTarget),
    onMouseLeave: () => hands.untip(),
    onFocus: (e: ReactFocusEvent<HTMLElement>) => hands.tip(id, e.currentTarget),
    onBlur: () => hands.untip(),
    onClick: () => hands.select(id),
  };
}

const Square = memo(function Square({ s, state, level, index, hands, onTake }: {
  s: Stigma; state: State; level: number | null; index?: number; hands: Hands; onTake(id: string): void;
}) {
  const l = levelLine(s, level);
  const min = s.levels[0]?.level;
  const anim = index === undefined ? {} : row(index, 6);
  return (
    <m.span {...anim} className="stg-sq-wrap"><button type="button" className={`stg-sq is-${state}${hands.focus === s.id ? " lit" : ""}${s.advanced ? " adv" : ""}${s.onlyClient ? " client" : ""}`}
      aria-label={`${l.name}${state === "lock" ? `, с ${min} уровня` : state === "on" ? ", взята" : ""}`} aria-pressed={hands.focus === s.id}
      draggable={state === "ok"} {...pointer(hands, s.id)} onDoubleClick={() => onTake(s.id)}
      onKeyDown={(e) => { if (e.key === "Enter" && e.shiftKey) { e.preventDefault(); onTake(s.id); } }}
      onDragStart={(e) => { e.dataTransfer.setData(DRAG, s.id); e.dataTransfer.effectAllowed = "copy"; hands.drag(s.id); }}
      onDragEnd={() => hands.drag(null)}>
      {l.icon ? <Icon name={l.icon} size={40} /> : <span className="icon blank" style={{ width: 40, height: 40 }} />}
      {state === "lock" && <i className="stg-lock">{min}</i>}
      {state !== "lock" && level !== null && <i className="stg-rank">{roman(s, level)}</i>}
    </button></m.span>
  );
});

// the game's window: normal slots in two columns of three; advanced ones two, one, two
const ADV_PLACE = ["a1", "a2", "a3", "a4", "a5"];
const SLOT_ICON = 36; // the frame's window at 74×70

function Slots({ kind, ids, ctx, pick, hands, onDrop }: {
  kind: "normal" | "advanced"; ids: string[]; ctx: Ctx; pick: Pick; hands: Hands; onDrop(id: string): void;
}) {
  const open = slotsAt(ctx.level)[kind];
  return (
    <div className={`stg-win-${kind}`} role="group" aria-label={`${kind === "normal" ? "Обычные" : "Продвинутые"} слоты: ${ids.length} из ${open}`}>
      {SLOT_LEVELS[kind].map((at, i) => {
        const place = kind === "advanced" ? ADV_PLACE[i] : undefined;
        const s = ids[i] ? ctx.stigmas.get(ids[i]) : undefined;
        if (i >= open) {
          return <div key={i} className="stg-slot locked" style={{ gridArea: place, backgroundImage: `url(${ui("locked")})` }} title={`Откроется на ${at} уровне`}>
            <span>{at}</span></div>;
        }
        if (!s) return <div key={i} className="stg-slot" style={{ gridArea: place, backgroundImage: `url(${ui(kind)})` }} />;
        const l = levelOf(ctx, pick, s.id) ?? s.levels[0];
        return (
          <m.div key={s.id} className={`stg-slot full${hands.focus === s.id ? " lit" : ""}`} style={{ gridArea: place, backgroundImage: `url(${ui(`${kind}_on`)})` }}
            initial={{ opacity: 0, scale: 0.86 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.24, ease: EASE }}>
            <button type="button" className="stg-slot-pick" aria-label={l.name} draggable {...pointer(hands, s.id)}
              onDragStart={(e) => { e.dataTransfer.setData(`${DRAG}-slot`, s.id); e.dataTransfer.setData(DRAG, s.id); e.dataTransfer.effectAllowed = "move"; hands.drag(`slot:${s.id}`); }}
              onDragEnd={() => hands.drag(null)}>
              {l.icon ? <Icon name={l.icon} size={SLOT_ICON} /> : <span className="icon blank" style={{ width: SLOT_ICON, height: SLOT_ICON }} />}
              <i className="stg-rank">{roman(s, l.level)}</i>
            </button>
            <button type="button" className="stg-slot-x" aria-label={`Снять ${l.name}`} title="Снять (и стигмы, которым она нужна)" onClick={() => onDrop(s.id)}><IconClose /></button>
          </m.div>
        );
      })}
    </div>
  );
}

// the tree's grid: a column is 60 px wide, a row 44 px high, a square 40 px
const COL = 60, ROW = 44, SQ = 40;
const W = 3 * COL + SQ, H = 6 * ROW;
const at = (i: number) => ({ x: PLACES[i].col * COL, y: ((PLACES[i].rows[0] + PLACES[i].rows[1]) / 2) * ROW });

function Tree({ tree, ctx, pick, hands, onTake }: { tree: string[]; ctx: Ctx; pick: Pick; hands: Hands; onTake(id: string): void }) {
  const edges = useMemo(() => treeEdges(tree, ctx.needs), [tree, ctx.needs]);
  // the arrows into the chosen stigma: the path it takes
  const path = hands.focus ? new Set([hands.focus, ...needsOf(ctx.needs, hands.focus)]) : null;
  return (
    <div className="stg-tree" style={{ width: W, height: H }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden>
        <defs>
          <marker id="stg-arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="context-stroke" /></marker>
        </defs>
        {edges.map(([a, b]) => {
          const p = at(a), q = at(b);
          const x1 = p.x + SQ + 3, x2 = q.x - 4, xm = q.x - (COL - SQ) / 2;
          const on = picked(pick, tree[a]) && picked(pick, tree[b]);
          const hot = path?.has(tree[a]) && path.has(tree[b]);
          return <path key={`${a}-${b}`} className={`stg-edge${on ? " on" : ""}${hot ? " hot" : ""}`} d={`M${x1},${p.y} H${xm} V${q.y} H${x2}`} markerEnd="url(#stg-arrow)" />;
        })}
      </svg>
      {tree.map((id, i) => {
        const s = ctx.stigmas.get(id);
        if (!s) return null;
        const { x, y } = at(i);
        return (
          <div key={i} className="stg-node" style={{ left: x, top: y - SQ / 2 }}>
            <Square s={s} state={stateOf(ctx, pick, s)} level={pickLevel(ctx, pick, s)} hands={hands} onTake={onTake} />
          </div>
        );
      })}
    </div>
  );
}

/** The stone's numbers in one line each: kinah, stigma shards, abyss points. */
function Costs({ l }: { l: StigmaLevel }) {
  return (
    <div className="stg-costs">
      {l.price != null && <span>Цена <b>{fmt(l.price)}</b> кинар</span>}
      <span><Icon name={SHARD_ICON} size={16} />Осколки стигм <b>{l.shards === null ? "?" : fmt(l.shards)}</b></span>
      {l.ap > 0 && <span><img src={ui("ap")} alt="" width={16} height={16} />Очки Бездны <b>{fmt(l.ap)}</b></span>}
    </div>
  );
}

/** The short note beside the square under the pointer. */
function TipBox({ tip, s, ctx, pick }: { tip: Tip; s: Stigma; ctx: Ctx; pick: Pick }) {
  const level = pickLevel(ctx, pick, s);
  const l = levelLine(s, level);
  const state = stateOf(ctx, pick, s);
  return (
    <m.div className="stg-tip" role="tooltip" style={{ left: tip.x, top: tip.y, translateX: tip.left ? "-100%" : 0 }}
      initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.14, ease: EASE }}>
      <b className={s.advanced ? "adv" : ""}>{l.name}</b>
      <small>{s.advanced ? "Продвинутая" : "Обычная"} стигма · с {l.level} уровня{s.onlyClient ? " · только в клиенте" : ""}</small>
      <Costs l={l} />
      {state === "lock" && <em className="dn">Нужен {s.levels[0].level} уровень</em>}
      {state === "full" && <em className="dn">Не хватает слотов для неё и нужных ей стигм</em>}
      {state === "on" && <em>Стоит в окне стигм</em>}
    </m.div>
  );
}

function Card({ s, ctx, pick, onTake, onDrop, onSelect, onLevel }: {
  s: Stigma; ctx: Ctx; pick: Pick; onTake(id: string): void; onDrop(id: string): void; onSelect(id: string): void; onLevel(level: number): void;
}) {
  const open = useOpenRef();
  const isOn = picked(pick, s.id);
  const [peek, setPeek] = useState<number | null>(null);
  const level = peek ?? pickLevel(ctx, pick, s) ?? s.levels[0].level;
  const l = levelLine(s, level);
  const state = stateOf(ctx, pick, s);
  const needs = ctx.needs.filter(([x]) => x === s.id).map(([, n]) => ctx.stigmas.get(n)).filter((x): x is Stigma => !!x);
  const usedBy = dependantsOf(ctx.needs, s.id).filter((x) => ctx.needs.some(([a, b]) => a === x && b === s.id)).map((x) => ctx.stigmas.get(x)).filter((x): x is Stigma => !!x);
  const rows: [string, string][] = [["Тип", kindText(s.kind)], ["Цель", targetText(s.target)], ["Расход", l.mp], ["Применение", castText(l.cast)],
    ["Перезарядка", cooldownText(l.cooldown)]].filter(([, v]) => v) as [string, string][];
  const ref = (x: Stigma) => {
    const n = levelLine(x, pickLevel(ctx, pick, x));
    return <button key={x.id} type="button" className={`stg-ref${picked(pick, x.id) ? " on" : ""}`} onClick={() => onSelect(x.id)}>
      {n.icon ? <Icon name={n.icon} size={26} /> : <span className="icon blank" style={{ width: 26, height: 26 }} />}<span>{n.name}</span></button>;
  };
  return (
    <m.article className="stg-detail" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.16, ease: EASE }}>
      <header className="stg-head">
        {l.icon ? <Icon name={l.icon} size={48} /> : <span className="icon blank" style={{ width: 48, height: 48 }} />}
        <div>
          <b className={s.advanced ? "adv" : ""}>{l.name}</b>
          <small>{s.advanced ? "Продвинутая стигма" : "Обычная стигма"} · с {l.level} уровня{s.onlyClient ? " · только в клиенте" : l.fromDb ? " · уровень из клиента" : ""}</small>
        </div>
      </header>

      <div className="stg-levels" role="radiogroup" aria-label="Уровень стигмы">
        {s.levels.map((x) => {
          const can = x.level <= ctx.level;
          return (
            <button key={x.level} type="button" role="radio" aria-checked={x.level === level} disabled={!can && isOn}
              className={`${x.level === level ? "on" : ""}${can ? "" : " far"}`} title={can ? `Стигма ${x.name}` : `С ${x.level} уровня`}
              onClick={() => { if (isOn && can) { setPeek(null); onLevel(x.level); } else setPeek(x.level); }}>
              {x.level === level && <Glide group={`stg-lv-${s.id}`} />}<span>{x.level}</span></button>
          );
        })}
      </div>

      {rows.length > 0 && <dl className="stg-dl">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>}
      {l.text && <p className="stg-text"><SkillText text={l.text} /></p>}
      {s.info.length > 0 && <ul className="stg-info">{s.info.map((x) => <li key={x}>{infoText(x)}</li>)}</ul>}

      <div className="stg-cost"><Costs l={l} /></div>

      {needs.length > 0 && <div className="stg-refs"><h5>Требует</h5>{needs.map(ref)}</div>}
      {usedBy.length > 0 && <div className="stg-refs"><h5>Нужна для</h5>{usedBy.map(ref)}</div>}

      <div className="stg-actions">
        {isOn ? <button type="button" className="btn" onClick={() => onDrop(s.id)}>Снять</button>
          : <button type="button" className="btn primary" disabled={state !== "ok"} onClick={() => onTake(s.id)}>
            {state === "lock" ? `С ${s.levels[0].level} уровня` : state === "full" ? "Не хватает слотов" : "Вставить в окно"}</button>}
        {l.stone && open && <button type="button" className="btn" onClick={() => open({ kind: "item", id: String(l.stone), name: l.name })}>Камень в базе</button>}
      </div>
    </m.article>
  );
}
