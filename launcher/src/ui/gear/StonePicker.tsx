// The manastones of the chosen item: slots as squares, under them a picker (a stat tab, a table of stones by grade) that opens
// for the slot touched. Example: docs/concepts/gear-stones/stones.html.
//
// Motion (the project's Motion helpers, ui/fx.tsx; all of it goes off with the system's reduced motion and the developer's «без плавности»):
//   the picker opens and closes   height (a grid row 0fr -> 1fr) and opacity, 220 ms, EASE, in CSS: Motion cannot measure «auto» inside a panel that is itself moving
//   a tab is chosen               the underline glides to it (Glide); the rows of the new tab arrive one by one (row)
//   a stone is put into a slot    its picture springs in from a half size; the counter and the sum pop
//   another slot is touched       nothing moves but the highlight (CSS): the picker stays where it is
import { m, useReducedMotion } from "motion/react";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";

import type { Stone } from "../../core/gear/engine";
import { statName } from "../../core/gear/labels";
import { stoneRows, stoneSum, stoneTabs } from "../../core/gear/stones";
import { Glide, Pop, row } from "../fx";
import { Icon } from "../Icon";
import { IconClose } from "../icons";

const GRADE_TITLE: Record<string, string> = { common: "Обычные", rare: "Редкие", legend: "Легендарные", unique: "Уникальные", epic: "Эпические", mythic: "Мифические" };

/** True when motion is to be left out: the system's reduced motion or the developer's «без плавности» (the html class App sets). */
function useCalm(): boolean {
  const reduce = useReducedMotion();
  return !!reduce || (typeof document !== "undefined" && document.documentElement.classList.contains("no-fade"));
}

export function StonePicker({ slots, optional, chosen, fits, onStone }: {
  slots: number; optional: number; chosen: (number | null)[]; fits: Stone[]; onStone(i: number, id: number | null): void;
}) {
  const byId = useMemo(() => new Map(fits.map((s) => [s.id, s])), [fits]);
  const tabs = useMemo(() => stoneTabs(fits), [fits]);
  const [open, setOpen] = useState<number | null>(null);
  const [stat, setStat] = useState("");
  const [best, setBest] = useState(false);
  const [cursor, setCursor] = useState(0);
  const last = useRef<number | null>(null);
  const panel = useRef<HTMLDivElement>(null);
  const tab = tabs.includes(stat) ? stat : tabs[0] ?? "";
  const groups = useMemo(() => stoneRows(fits, tab, best), [fits, tab, best]);
  const flat = useMemo(() => groups.flatMap((g) => g.rows), [groups]);
  const worn = chosen.map((id) => (id === null ? null : byId.get(id) ?? null));
  const calm = useCalm();
  const shown = useRef(0); // the slot the picker was last open for: it is still on screen while it closes
  if (open !== null) shown.current = open;
  const slotNo = open ?? shown.current;
  // the picker stays mounted a moment after it is closed, and is opened one frame after it is mounted: that is what the CSS transition needs
  const [mounted, setMounted] = useState(false);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    if (open !== null) {
      setMounted(true);
      const frame = requestAnimationFrame(() => requestAnimationFrame(() => setExpanded(true)));
      return () => cancelAnimationFrame(frame);
    }
    setExpanded(false);
    const timer = setTimeout(() => setMounted(false), calm ? 0 : 200);
    return () => clearTimeout(timer);
  }, [open !== null]); // eslint-disable-line react-hooks/exhaustive-deps -- only the opening and the closing, not the slot

  useEffect(() => { setOpen(null); }, [slots]); // another item
  useEffect(() => { setCursor(0); }, [tab, best]);
  if (slots === 0) return null;

  const put = (id: number) => {
    if (open === null) return;
    onStone(open, id);
    last.current = id;
    const next = Array.from({ length: slots }, (_, i) => i).find((i) => i > open && (i === open ? false : chosen[i] === null || chosen[i] === undefined));
    setOpen(next ?? open);
  };
  const wantFocus = useRef(false); // a slot was chosen: the focus goes into the picker as soon as it is on screen
  const choose = (i: number) => {
    setOpen(i);
    const s = worn[i];
    if (s) setStat(s.stat);
    wantFocus.current = true;
  };
  useEffect(() => {
    if (open === null || !mounted || !wantFocus.current) return;
    wantFocus.current = false;
    panel.current?.focus({ preventScroll: true });
  }, [open, mounted]);
  const key = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(flat.length - 1, c + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
    else if (e.key === "Enter" && flat[cursor]) { e.preventDefault(); put(flat[cursor].id); }
    else if (e.key === "Escape") { e.stopPropagation(); const at = open; setOpen(null); if (at !== null) requestAnimationFrame(() => (document.querySelector(`.gear-slot[data-slot="${at}"]`) as HTMLElement | null)?.focus()); }
  };
  const sum = stoneSum(worn);
  let index = -1;

  return (
    <div className="gear-stones">
      <div className="gear-stones-head">
        <span>Магические камни</span>
        <em><Pop value={worn.filter(Boolean).length} /> из {slots}{optional ? ` · доп. слот: ${optional}` : ""}</em>
      </div>
      <div className="gear-slots">
        {Array.from({ length: slots }, (_, i) => {
          const s = worn[i];
          const extra = i >= slots - optional;
          return (
            <div key={i} role="button" tabIndex={0} data-slot={i} className={`gear-slot${open === i ? " open" : ""}${extra ? " optional" : ""}`} aria-pressed={open === i}
              aria-label={s ? `Слот ${i + 1}: ${s.name}` : `Слот ${i + 1}: ${extra ? "дополнительный, " : ""}пусто`}
              onClick={() => (open === i ? setOpen(null) : choose(i))}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (open === i) setOpen(null); else choose(i); }
                else if ((e.key === "Delete" || e.key === "Backspace") && s) { e.preventDefault(); onStone(i, null); }
                else if (e.key === "Escape" && open !== null) { e.stopPropagation(); setOpen(null); }
              }}>
              <span className="gear-slot-cell">{s ? <m.span key={s.id} className="gear-slot-fill" initial={calm ? false : { scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", stiffness: 600, damping: 18 }}><Icon name={s.icon} size={32} /></m.span> : extra ? "?" : ""}</span>
              <span className="gear-slot-text">
                {s ? <><b className={`g-${s.grade}`}>{statName(s.stat)} +{s.value}</b><span>ур. {s.level}</span></>
                  : <><b className="gear-slot-none">{extra ? "Доп. слот" : "Пусто"}</b><span>выбрать камень</span></>}
              </span>
              {s && <button type="button" className="gear-slot-x" tabIndex={-1} aria-label="Убрать камень" title="Убрать камень (Delete)" onClick={(e) => { e.stopPropagation(); onStone(i, null); }}><IconClose /></button>}
            </div>
          );
        })}
      </div>
      <div className="gear-stones-tools">
        <button type="button" className="btn" disabled={last.current === null} title="Поставить последний выбранный камень во все пустые слоты"
          onClick={() => { const id = last.current; if (id !== null) chosen.forEach((x, i) => { if (x === null || x === undefined) onStone(i, id); }); }}>Один камень во все слоты</button>
        <button type="button" className="btn" disabled={!worn.some(Boolean)} onClick={() => chosen.forEach((x, i) => { if (x !== null && x !== undefined) onStone(i, null); })}>Очистить</button>
      </div>
      {mounted && (
        <div className={`gear-pick-wrap${expanded ? " on" : ""}`}>
          <div className="gear-pick-clip">
        <div className="gear-pick" ref={panel} tabIndex={-1} onKeyDown={key} aria-label={`Камень для слота ${slotNo + 1}`}>
            <div className="gear-pick-head">
              <span>Слот <b>{slotNo + 1}</b></span>
              <span className="spacer" />
              <label><input type="checkbox" checked={best} onChange={(e) => setBest(e.target.checked)} /> только самый сильный камень</label>
              <button type="button" className="gear-pick-x" aria-label="Закрыть выбор" onClick={() => setOpen(null)}><IconClose /></button>
            </div>
            <div className="gear-pick-tabs" role="tablist">
              {tabs.map((t) => <button key={t} type="button" role="tab" aria-selected={t === tab} tabIndex={t === tab ? 0 : -1} className={t === tab ? "on" : ""} onClick={() => setStat(t)}
                onKeyDown={(e) => {
                  const to = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
                  if (!to) return;
                  e.preventDefault();
                  const next = tabs[(tabs.indexOf(t) + to + tabs.length) % tabs.length];
                  setStat(next);
                  (e.currentTarget.parentElement?.querySelector(`[data-tab="${next}"]`) as HTMLElement | null)?.focus();
                }} data-tab={t}>{statName(t)}{t === tab && !calm && <Glide group="stone-tab" className="gear-tab-line" />}</button>)}
            </div>
            <div className="gear-pick-body" key={tab + String(best)}>
              {flat.length === 0 && <p className="dbt-note">Для этого предмета камней этой характеристики нет.</p>}
              {groups.map((g) => (
                <Fragment key={g.grade}>
                  <div className={`gear-pick-group g-${g.grade}`}>{GRADE_TITLE[g.grade] ?? g.grade}</div>
                  {g.rows.map((s) => {
                    index += 1;
                    const at = index;
                    const here = chosen[slotNo] === s.id;
                    return (
                      <m.button key={s.id} type="button" tabIndex={-1} className={`gear-pick-row${at === cursor ? " cur" : ""}${here ? " here" : ""}`} {...(calm ? {} : row(at, 6))}
                        onPointerEnter={() => setCursor(at)} onClick={() => put(s.id)}>
                        <span className="lv">{s.level}</span>
                        <Icon name={s.icon} size={30} />
                        <span className={`g-${s.grade}`}>{s.name}</span>
                        {here ? <em>в слоте</em> : chosen.includes(s.id) ? <em>стоит</em> : null}
                      </m.button>
                    );
                  })}
                </Fragment>
              ))}
            </div>
          </div>
          </div>
        </div>
      )}
      <div className="gear-stones-sum">{sum.length ? <>Камни дают: {sum.map(([s, v], i) => <Fragment key={s}>{i ? ", " : ""}<b>{statName(s)} +<Pop value={v} /></b></Fragment>)}</> : "Камни пока не выбраны."}</div>
    </div>
  );
}
