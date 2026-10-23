import { useEffect, useRef } from "react";

import { DAY, ScheduleEvent, startsAt, weekStart } from "../../core/schedule/reminders";
import { bellKey, DAY_NAMES, endOf } from "../../core/schedule/timing";
import { IconClose, IconPencil } from "../icons";
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

/** The card of one event: its time on both clocks, the countdown, the bell and the next times. */
export function Drawer({ event, schedule, onClose, onEdit, onDelete, onDeleteSeries }: Props) {
  const { now } = schedule;
  const slot = slotOf(event)!;
  const own = schedule.isOwn(event);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => { panel.current?.focus(); }, [event]);

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
  const bell = schedule.bells.has(bellKey(event));
  const days = own ? schedule.seriesDays(event) : [event.day];

  return (
    <aside className="sch-drawer" ref={panel} tabIndex={-1} aria-label={`Событие «${event.name}»`}
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
      <div className="hd"><span className="muted">{own ? "Своё событие" : "Событие"}</span><span className="spacer" />
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
        <button className={`sch-switch${bell ? " on" : ""}`} role="switch" aria-checked={bell} onClick={() => schedule.toggleBell(event)}>
          <i /> {bell ? "Напомню заранее и когда начнётся" : "Не напоминаю"}
        </button>
        <div className="hint">За сколько минут — в настройках, «Когда нашлось».</div>
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
        {own ? (
          <>
            <button className="btn primary" onClick={() => onEdit(event)}><IconPencil />Изменить</button>
            <button className="btn" onClick={() => onDelete(event)}>Удалить только этот день</button>
            {days.length > 1 && <button className="btn danger-text" onClick={() => onDeleteSeries(event)}>Удалить все повторы</button>}
          </>
        ) : (
          <button className="btn" onClick={() => onDelete(event)}>Скрыть это событие</button>
        )}
      </div>
    </aside>
  );
}

