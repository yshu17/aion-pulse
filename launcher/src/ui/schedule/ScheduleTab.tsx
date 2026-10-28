import { useCallback, useEffect, useRef, useState } from "react";

import { DAY, DAYS, dayStart, ScheduleEvent, weekday, weekStart } from "../../core/schedule/reminders";
import { bellKey } from "../../core/schedule/timing";
import { IconBell, IconCheck, IconCopy, IconLeft, IconPencil, IconPlus, IconRight, IconClose } from "../icons";
import { Drawer } from "./Drawer";
import { EventForm } from "./EventForm";
import { Ghost, Grid } from "./Grid";
import { hm } from "./layout";
import { AnimatePresence } from "motion/react";
import { Glide } from "../fx";
import { Presence } from "../motion";
import { ResetsMenu } from "./ResetsMenu";
import { SourceMenu } from "./SourceMenu";
import { announce, useYields } from "./popover";
import { Ribbon } from "./Ribbon";
import { CHIP_TONE, CHIPS, Draft, Schedule } from "./useSchedule";

type View = "3days" | "week";
const MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const SWATCH: Record<string, string> = { blue: "#6f9bff", green: "#5fd38d", teal: "#4fd1cf", amber: "#f5b544", purple: "#b58cff" };
const NARROW = 1000;
const CHIPS_FIT = 1440; // below it the filter chips fold into one «Фильтры» button
const FORM_WIDTH = 480;

interface FormState {
  mode: "create" | "edit";
  title: string;
  draft: Draft;
  old?: ScheduleEvent;
  placement: { kind: "float"; left: number; top: number } | { kind: "sheet" };
}

interface MenuState {
  event: ScheduleEvent;
  x: number;
  y: number;
}

/** True while the window is narrower than `width`. */
function useNarrow(width = NARROW): boolean {
  const [narrow, setNarrow] = useState(() => window.innerWidth < width);
  useEffect(() => {
    const on = () => setNarrow(window.innerWidth < width);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, [width]);
  return narrow;
}

const rangeText = (from: number, to: number) => {
  const a = new Date(from);
  const b = new Date(to);
  if (from === to) return `${a.getUTCDate()} ${MONTHS[a.getUTCMonth()]}`;
  return a.getUTCMonth() === b.getUTCMonth()
    ? `${a.getUTCDate()} – ${b.getUTCDate()} ${MONTHS[b.getUTCMonth()]}`
    : `${a.getUTCDate()} ${MONTHS[a.getUTCMonth()]} – ${b.getUTCDate()} ${MONTHS[b.getUTCMonth()]}`;
};

export function ScheduleTab({ schedule }: { schedule: Schedule }) {
  const narrow = useNarrow();
  const chipsFold = useNarrow(CHIPS_FIT);
  const [view, setView] = useState<View>(() => (window.innerWidth < NARROW ? "3days" : "week"));
  const [offset, setOffset] = useState(0);
  const [zone, setZone] = useState<"msk" | "local">("msk");
  const [selected, setSelected] = useState<ScheduleEvent | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [ghost, setGhost] = useState<Ghost | null>(null);
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [chipsOpen, setChipsOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  const today = dayStart(schedule.now);
  const first = view === "week" ? weekStart(schedule.now) + offset * 7 * DAY : today + offset * 3 * DAY;
  const count = view === "week" ? 7 : 3;
  const days = Array.from({ length: count }, (_, i) => {
    const date = first + i * DAY;
    return { key: DAYS[weekday(date)], date };
  });
  const changeView = (next: View) => { setView(next); setOffset(0); };

  const closeForm = useCallback(() => { setForm(null); setGhost(null); }, []);
  const closeAll = useCallback(() => { setForm(null); setGhost(null); setMenu(null); setChipsOpen(false); }, []);
  useYields("grid", closeAll); // the link and resets menus close the form, the right-click menu and the filters

  const openCreate = (draft: Draft, near: Ghost | null, title = "Новое событие") => {
    setMenu(null);
    setSelected(null);
    const sheet = narrow;
    announce("grid");
    setTimeout(() => { // after the ghost card is on screen
      const el = near ? document.querySelector<HTMLElement>("[data-ghost]") : null;
      let placement: FormState["placement"] = { kind: "float", left: Math.max(12, window.innerWidth - FORM_WIDTH - 24), top: 150 };
      if (el) {
        const r = el.getBoundingClientRect();
        const left = r.left - FORM_WIDTH - 14 >= 12 ? r.left - FORM_WIDTH - 14 : Math.min(window.innerWidth - FORM_WIDTH - 12, r.right + 14);
        placement = { kind: "float", left, top: Math.max(70, Math.min(r.top - 150, window.innerHeight - 560)) };
      }
      setForm({ mode: "create", title, draft, placement: sheet ? { kind: "sheet" } : placement });
    }, 0);
  };

  const openEdit = (event: ScheduleEvent) => {
    announce("grid");
    setMenu(null);
    setSelected(null);
    setGhost(null);
    setForm({ mode: "edit", title: "Изменить событие", draft: schedule.draftOf(event), old: event, placement: narrow ? { kind: "sheet" } : { kind: "float", left: Math.max(12, window.innerWidth - FORM_WIDTH - 24), top: 150 } });
  };

  const newByButton = () => {
    const minute = Math.min(22 * 60, (Math.floor((schedule.now - today) / 3_600_000) + 1) * 60);
    openCreate({ name: "", start: hm(minute), end: minute + 60 >= 1440 ? "24:00" : hm(minute + 60), days: [DAYS[weekday(schedule.now)]], chip: "Своё", bell: true, lead: schedule.defaultLead }, null);
  };

  const onGhost = (g: Ghost | null, done: boolean) => {
    setGhost(g);
    if (done && g) {
      openCreate({ name: "", start: hm(g.s), end: g.e >= 1440 ? "24:00" : hm(g.e), days: [g.day], chip: "Своё", bell: true, lead: schedule.defaultLead }, g);
    }
  };

  const save = (draft: Draft) => {
    if (form?.mode === "edit" && form.old) schedule.update(form.old, draft);
    else schedule.create(draft);
    closeForm();
  };

  const copyAsOwn = (event: ScheduleEvent) => {
    setMenu(null);
    const d = schedule.draftOf(event);
    openCreate({ ...d, chip: "Своё", days: [event.day], bell: schedule.bells.has(bellKey(event)) }, null, "Копия как своё событие");
  };

  useEffect(() => { // Esc closes what is open on top
    const esc = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (chipsOpen) setChipsOpen(false);
      else if (menu) setMenu(null);
      else if (form) closeForm();
      else if (selected) setSelected(null);
    };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [chipsOpen, menu, form, selected, closeForm]);

  useEffect(() => { // a menu closes when the pointer goes elsewhere or the window scrolls
    if (!menu) return;
    const off = (e: Event) => { if (!(e.target as HTMLElement).closest?.(".sch-menu")) setMenu(null); };
    window.addEventListener("pointerdown", off);
    window.addEventListener("blur", () => setMenu(null));
    return () => window.removeEventListener("pointerdown", off);
  }, [menu]);

  useEffect(() => { // the filter list of a narrow window closes on a click elsewhere
    if (!chipsOpen) return;
    const off = (e: Event) => { if (!(e.target as HTMLElement).closest?.(".sch-chips")) setChipsOpen(false); };
    window.addEventListener("pointerdown", off);
    return () => window.removeEventListener("pointerdown", off);
  }, [chipsOpen]);

  const hidden = schedule.hiddenCount;
  return (
    <main className="sch" ref={root}>
      <div className="sch-bar">
        <button className="sch-nav" aria-label="Назад" onClick={() => setOffset(offset - 1)}><IconLeft /></button>
        <button className="sch-nav" aria-label="Вперёд" onClick={() => setOffset(offset + 1)}><IconRight /></button>
        <h2 className="range">{rangeText(days[0].date, days[days.length - 1].date)}</h2>
        <button className="btn" onClick={() => setOffset(0)}>Сегодня</button>
        <div className="segmented" role="radiogroup" aria-label="Сколько дней показывать">
          {([["3days", "3 дня"], ["week", "Неделя"]] as [View, string][]).map(([v, label]) => (
            <button key={v} role="radio" aria-checked={view === v} className={view === v ? "on" : ""} onClick={() => changeView(v)}>{view === v && <Glide group="seg-view" />}<span>{label}</span></button>
          ))}
        </div>
        <div className={`sch-chips${chipsFold ? " drop" : ""}${chipsOpen ? " open" : ""}`} role="group" aria-label="Что показывать">
          {chipsFold && (
            <button className="sch-chip" aria-expanded={chipsOpen} onClick={() => { announce("grid"); setChipsOpen(!chipsOpen); }}>
              <b>Фильтры</b><em>{CHIPS.length - schedule.hiddenGroups.size} из {CHIPS.length}</em>
            </button>
          )}
          {(!chipsFold || chipsOpen) && (
            <div className="list">
              {CHIPS.map((chip) => {
                const on = !schedule.hiddenGroups.has(chip);
                return (
                  <button key={chip} className={`sch-chip${on ? "" : " off"}`} aria-pressed={on} onClick={() => schedule.toggleChip(chip)}>
                    <span className="cb" style={{ background: on ? SWATCH[CHIP_TONE[chip]] : "transparent" }}>{on && <IconCheck />}</span>
                    <b>{chip}</b><em>{schedule.counts[chip]}</em>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <span className="spacer" />
        <SourceMenu schedule={schedule} />
        <button className={`btn sq bell-all${schedule.allBells ? " on" : ""}`} aria-pressed={schedule.allBells} onClick={schedule.toggleAllBells}
          title={schedule.allBells ? "Выключить напоминания обо всех событиях и откатах" : "Напоминать обо всех событиях и откатах"}
          aria-label="Напоминать обо всех событиях и откатах"><IconBell on={schedule.allBells} /></button>
        <ResetsMenu schedule={schedule} />
        <button className="btn primary" onClick={newByButton}><IconPlus />Событие</button>
      </div>

      <Ribbon schedule={schedule} zone={zone} onZone={setZone} onSelect={setSelected} />

      <Grid days={days} schedule={schedule} zone={zone} selected={selected} ghost={ghost} onGhost={onGhost}
        onSelect={(e) => { setForm(null); setGhost(null); setSelected(e); }} onEdit={openEdit}
        onDelete={schedule.removeOne} onMenu={(event, x, y) => { announce("grid"); setMenu({ event, x, y }); }} />

      <div className="sch-legend">
        <span className="hintbar">Потяни по пустому месту сетки: появится новое событие. Клик по событию — подробности.</span>
        <span className="spacer" />
        {schedule.site && schedule.site.state !== "busy" && (
          <span className={`sch-site ${schedule.site.state}`} role="status">{schedule.site.text}
            {schedule.site.state === "changed" && <button className="link accent" onClick={() => schedule.openLink()}>Открыть ссылку</button>}
          </span>
        )}
        {hidden > 0 && <button className="link" onClick={schedule.restoreHidden}>Удалено событий сервера: {hidden}. Вернуть все</button>}
        <span className="own-legend"><i />своё событие</span>
      </div>

      <AnimatePresence>
        {selected && !form && (
          <Drawer key="drawer" event={selected} schedule={schedule} onClose={() => setSelected(null)} onEdit={openEdit}
            onDelete={(e) => { schedule.removeOne(e); setSelected(null); }} onDeleteSeries={(e) => { schedule.removeSeries(e); setSelected(null); }} />
        )}
      </AnimatePresence>

      <Presence show={form !== null}>
        {form && (
          <EventForm title={form.title} draft={form.draft} placement={form.placement} onChange={(draft) => setForm({ ...form, draft })}
            onSave={save} onCancel={closeForm} />
        )}
      </Presence>

      <Presence show={menu !== null}>
        {menu && <ContextMenu menu={menu} schedule={schedule} onEdit={openEdit} onCopy={copyAsOwn} onClose={() => setMenu(null)} />}
      </Presence>

      <Presence show={schedule.undo !== null}>
        {schedule.undo && (
          <div className="sch-undo" role="status">
            <span>{schedule.undo.label}</span>
            <button className="btn primary" onClick={schedule.undoLast}>Отменить удаление</button>
            <UndoLeft until={schedule.undo.until} />
          </div>
        )}
      </Presence>
    </main>
  );
}

function ContextMenu({ menu, schedule, onEdit, onCopy, onClose }: {
  menu: MenuState; schedule: Schedule; onEdit(e: ScheduleEvent): void; onCopy(e: ScheduleEvent): void; onClose(): void;
}) {
  const { event } = menu;
  const own = schedule.isOwn(event);
  const bell = schedule.bells.has(bellKey(event));
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => { list.current?.querySelector<HTMLButtonElement>("button")?.focus(); }, []);
  const left = Math.min(menu.x, window.innerWidth - 290);
  const top = Math.min(menu.y, window.innerHeight - (own ? 230 : 160));
  const act = (fn: () => void) => () => { onClose(); fn(); };
  const series = schedule.seriesDays(event).length > 1;
  return (
    <div className="sch-menu" ref={list} role="menu" style={{ left, top }}
      onKeyDown={(e) => {
        const items = [...(list.current?.querySelectorAll<HTMLButtonElement>("button") ?? [])];
        const at = items.indexOf(document.activeElement as HTMLButtonElement);
        if (e.key === "ArrowDown") { e.preventDefault(); items[(at + 1) % items.length]?.focus(); }
        if (e.key === "ArrowUp") { e.preventDefault(); items[(at - 1 + items.length) % items.length]?.focus(); }
      }}>
      <button role="menuitem" onClick={act(() => onEdit(event))}><IconPencil />Изменить</button>
      <button role="menuitem" onClick={act(() => onCopy(event))}><IconCopy />{own ? "Дублировать на другие дни" : "Копировать как своё"}</button>
      <button role="menuitem" onClick={act(() => schedule.toggleBell(event))}><IconBell on={bell} />{bell ? "Не напоминать" : "Напоминать"}<span className="k">{bell ? "вкл" : ""}</span></button>
      <hr />
      <button role="menuitem" className="red" onClick={act(() => schedule.removeOne(event))}><IconClose />{series ? "Удалить только этот день" : "Удалить"}<span className="k">Del</span></button>
      {series && <button role="menuitem" className="red" onClick={act(() => schedule.removeSeries(event))}><IconClose />Удалить все повторы</button>}
    </div>
  );
}

/** Seconds left to bring a deleted event back. */
function UndoLeft({ until }: { until: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  return <span className="muted">{Math.max(0, Math.ceil((until - now) / 1000))} с</span>;
}
