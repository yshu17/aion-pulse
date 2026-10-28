import { m } from "motion/react";
import { FADE, SPRING } from "../fx";
import { useEffect, useRef, useState } from "react";

import { DAY, ScheduleEvent, startsAt, weekStart } from "../../core/schedule/reminders";
import { bellKey, DAY_NAMES, endOf } from "../../core/schedule/timing";
import { IconClose, IconPencil } from "../icons";
import { LeadPicker } from "./EventForm";
import { zoneShift } from "./Grid";
import { countdown, hm, slotOf, toneOf } from "./layout";
import { chipOf, Schedule } from "./useSchedule";

const SWATCH: Record<string, string> = { blue: "#6f9bff", green: "#5fd38d", teal: "#4fd1cf", amber: "#f5b544", purple: "#b58cff", orange: "#ff8c1a", gray: "#8c919c" };
const MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const SHORT = { mon: "Пн", tue: "Вт", wed: "Ср", thu: "Чт", fri: "Пт", sat: "Сб", sun: "Вс" } as Record<string, string>;

interface Props {
  event: ScheduleEvent;
  schedule: Schedule;
  onClose(): void;
  onEdit(event: ScheduleEvent): void;
  onDelete(event: ScheduleEvent): void;
  onDeleteSeries(event: ScheduleEvent): void;
}

/**
 * The card of one event: its time on both clocks, the countdown, the bell and the next times. The bell and its lead are
 * a draft: «Сохранить» keeps them; a press anywhere else in the program, Esc or the cross close the card without them.
 */
export function Drawer({ event, schedule, onClose, onEdit, onDelete, onDeleteSeries }: Props) {
  const { now } = schedule;
  const slot = slotOf(event)!;
  const own = schedule.isOwn(event);
  const edited = schedule.isEdited(event);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => { panel.current?.focus(); }, [event]);
  useEffect(() => { // a press outside the card closes it, nothing saved
    const off = (e: Event) => { if (!(e.target as HTMLElement).closest?.(".sch-drawer")) onClose(); };
    window.addEventListener("pointerdown", off);
    return () => window.removeEventListener("pointerdown", off);
  }, [onClose]);

  // the next three occurrences from now
  const monday = weekStart(now);
  const runs: { start: number; end: number }[] = [];
  for (let w = -1; w < 3 && runs.length < 3; w++) {
    const start = startsAt(event, monday + w * 7 * DAY);
    const end = endOf(event, start);
    if (end > now) runs.push({ start, end });
  }
  const first = runs[0];
  const shift = zoneShift("local");
  const local = (m: number) => hm((((m + shift) % 1440) + 1440) % 1440);
  const date = first ? new Date(first.start) : null;
  const tone = toneOf(event);
  const savedBell = schedule.bells.has(bellKey(event));
  const savedLead = schedule.leadOf(event);
  const [bell, setBell] = useState(savedBell);
  const [lead, setLead] = useState(savedLead);
  useEffect(() => { setBell(savedBell); setLead(savedLead); }, [event]); // eslint-disable-line react-hooks/exhaustive-deps -- another event: its own values
  const changed = bell !== savedBell || (bell && lead !== savedLead);
  const save = () => {
    if (bell !== savedBell) schedule.toggleBell(event);
    if (bell && lead !== savedLead) schedule.setLead(event, lead);
    onClose();
  };
  const days = schedule.seriesDays(event);

  return (
    <m.aside className="sch-drawer" ref={panel} initial={{ x: 56, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 56, opacity: 0, transition: FADE }}
      transition={{ ...SPRING, opacity: FADE }} tabIndex={-1} aria-label={`Событие «${event.name}»`}
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
      <div className="hd"><span className="muted">{own ? "Своё событие" : edited ? "Событие, изменено тобой" : "Событие"}</span><span className="spacer" />
        <button className="sch-x" aria-label="Закрыть карточку" onClick={onClose}><IconClose /></button></div>
      <h2><span className="dot" style={{ background: SWATCH[tone] }} />{event.name}</h2>
      <div className="muted sub">
        {date ? `${DAY_NAMES[event.day]}, ${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]}` : DAY_NAMES[event.day]} ·{" "}
        {own ? "видно только тебе" : `группа «${chipOf(event)}»`}
      </div>

      <div className="facts">
        <div className="time">{event.start}–{hm(slot.e === 1440 ? 0 : slot.e)} <small>МСК</small></div>
        <div>{local(slot.s)}–{local(slot.e === 1440 ? 0 : slot.e)} <span className="muted">{shift === 0 ? "у тебя то же время" : "у тебя"}</span></div>
        {first && <div className="cd">{first.start <= now ? "идёт сейчас" : `через ${countdown(first.start - now)}`}</div>}
      </div>

      <div>
        <div className="lbl">Напоминание</div>
        <button className={`sch-switch${bell ? " on" : ""}`} role="switch" aria-checked={bell} onClick={() => setBell(!bell)}>
          <i /> {bell ? "Напомню заранее и когда начнётся" : "Не напоминаю"}
        </button>
        {bell && <LeadPicker value={lead} onChange={setLead} />}
      </div>

      <div>
        <div className="lbl">{days.length > 1 ? `Повторяется: ${days.map((d) => SHORT[d]).join(", ")}` : "Ближайшие разы"}</div>
        {runs.map((r) => {
          const d = new Date(r.start);
          return <div key={r.start} className="occ"><b>{SHORT[Object.keys(SHORT)[(d.getUTCDay() + 6) % 7]]} {d.getUTCDate()}</b> · {hm((r.start / 60000) % 1440)} МСК</div>;
        })}
      </div>

      <span className="spacer" />
      <div className="actions">
        <button className="btn primary" disabled={!changed} onClick={save} title={changed ? "Сохранить напоминание" : "Нечего сохранять"}>Сохранить</button>
        <button className="btn" onClick={() => onEdit(event)}><IconPencil />Изменить</button>
        <button className="btn" onClick={() => onDelete(event)}>{days.length > 1 ? "Удалить только этот день" : "Удалить"}</button>
        {days.length > 1 && <button className="btn danger-text" onClick={() => onDeleteSeries(event)}>Удалить все повторы</button>}
      </div>
    </m.aside>
  );
}

