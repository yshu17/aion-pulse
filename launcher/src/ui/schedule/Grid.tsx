import { useRef } from "react";

import { dayStart, ScheduleEvent } from "../../core/schedule/reminders";
import { bellKey, localZone, MSK_OFFSET } from "../../core/schedule/timing";
import { IconBell, IconClose, IconPencil } from "../icons";
import { FOLD_MID, FOLD_MID_Y, FOLD_TOP, GRID_H, hm, minuteAt, placeDay, toneOf, yOf } from "./layout";
import type { Schedule } from "./useSchedule";

export interface DayColumn {
  key: string; // mon … sun
  date: number; // midnight of this day, naive MSK ms
}

export interface Ghost {
  day: string;
  s: number;
  e: number;
}

const DAY_SHORT: Record<string, string> = { mon: "Пн", tue: "Вт", wed: "Ср", thu: "Чт", fri: "Пт", sat: "Сб", sun: "Вс" };
const HOURS = [2, 4, 10, 12, 14, 16, 18, 20, 22, 24];

/** Minutes to add to an MSK time of day to show it on this computer's clock. */
export function zoneShift(zone: "msk" | "local"): number {
  return zone === "msk" ? 0 : localZone(Date.now()) - MSK_OFFSET;
}
const shown = (minute: number, shift: number) => hm((((minute + shift) % 1440) + 1440) % 1440);

interface Props {
  days: DayColumn[];
  schedule: Schedule;
  zone: "msk" | "local";
  selected: ScheduleEvent | null;
  ghost: Ghost | null;
  onGhost(ghost: Ghost | null, done: boolean): void;
  onSelect(event: ScheduleEvent): void;
  onEdit(event: ScheduleEvent): void;
  onDelete(event: ScheduleEvent): void;
  onMenu(event: ScheduleEvent, x: number, y: number): void;
}

export function Grid({ days, schedule, zone, selected, ghost, onGhost, onSelect, onEdit, onDelete, onMenu }: Props) {
  const { now } = schedule;
  const today = dayStart(now);
  const nowMinute = Math.floor((now - today) / 60000);
  const shift = zoneShift(zone);
  const drag = useRef<{ day: string; from: number; rect: DOMRect } | null>(null);

  const down = (e: React.PointerEvent<HTMLDivElement>, day: string) => {
    if (e.button !== 0 || (e.target as HTMLElement).closest(".sch-card, .sch-ghost")) return; // only on an empty place
    const rect = e.currentTarget.getBoundingClientRect();
    const minute = minuteAt(e.clientY - rect.top);
    if (minute === null) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { day, from: minute, rect };
    onGhost({ day, s: minute, e: Math.min(1440, minute + 60) }, false);
  };
  const move = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d) return;
    const minute = minuteAt(Math.min(GRID_H, Math.max(0, e.clientY - d.rect.top)));
    if (minute === null) return;
    const s = Math.min(d.from, minute);
    const end = Math.max(d.from, minute);
    onGhost({ day: d.day, s, e: Math.max(end, s + 30) }, false);
  };
  const up = () => {
    if (!drag.current) return;
    drag.current = null;
    if (ghost) onGhost({ ...ghost, e: Math.min(1440, ghost.e) }, true);
  };

  return (
    <div className="sch-grid card" style={{ ["--n" as string]: days.length }}>
      <div />
      {days.map((d) => (
        <div key={d.key + d.date} className={`sch-dh${d.date === today ? " today" : ""}`}>
          {DAY_SHORT[d.key]} <b>{new Date(d.date).getUTCDate()}</b>
        </div>
      ))}

      <div className="sch-axis" style={{ height: GRID_H }} aria-hidden>
        {HOURS.map((h) => {
          const y = yOf(h * 60);
          if (days.some((d) => d.date === today) && Math.abs(y - yOf(nowMinute)) < 16) return null;
          return <span key={h} style={{ top: y }}>{String(h % 24).padStart(2, "0")}:00</span>;
        })}
        <span className="quiet" style={{ top: FOLD_MID_Y + FOLD_MID / 2 }}>04–10<br />тихо</span>
        {days.some((d) => d.date === today) && <span className="nowchip" style={{ top: yOf(nowMinute) }}>{shown(nowMinute, shift)}</span>}
      </div>

      {days.map((d) => {
        const own = schedule.visible.filter((e) => e.day === d.key);
        const placed = placeDay(own);
        const isToday = d.date === today;
        const resets = schedule.resets.filter((r) => r.when === "daily" || r.day === d.key);
        return (
          <div key={d.key + d.date} className={`sch-col${isToday ? " today" : ""}`} style={{ height: GRID_H }}
            onPointerDown={(e) => down(e, d.key)} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
            {HOURS.map((h) => <div key={h} className="sch-hl" style={{ top: yOf(h * 60) }} />)}
            <div className="sch-fold" style={{ top: 0, height: FOLD_TOP }} />
            <div className="sch-fold" style={{ top: FOLD_MID_Y, height: FOLD_MID }} />
            <div className="sch-resets" style={{ top: FOLD_MID_Y + 11 }}>
              {resets.map((r) => (
                <span key={r.name + r.when} title={`${r.name} в ${r.time} МСК`}>
                  {r.when === "daily" ? "Откат" : r.name.includes("БП") ? "+ БП" : "+ неделя"}
                </span>
              ))}
            </div>
            {placed.map((p) => {
              const top = yOf(p.s) + 1;
              const height = yOf(p.e) - top - 1;
              const width = 100 / p.lanes;
              const past = d.date + p.e * 60000 <= now;
              const isOwn = schedule.isOwn(p.event);
              const isSel = selected !== null && schedule.keyOf(selected) === schedule.keyOf(p.event);
              const bell = schedule.bells.has(bellKey(p.event));
              const tall = height >= 44;
              const label = `${p.event.name}, ${DAY_SHORT[d.key]} ${shown(p.s, shift)}–${shown(p.e === 1440 ? 0 : p.e, shift)}`;
              return (
                <div key={schedule.keyOf(p.event)} className={`sch-card t-${toneOf(p.event)}${past ? " past" : ""}${isOwn ? " own" : ""}${isSel ? " sel" : ""}${bell ? " belled" : ""}`}
                  style={{ top, height, left: `calc(${p.lane * width}% + 2px)`, width: `calc(${width}% - 4px)` }}
                  role="button" tabIndex={0} aria-label={label} title={label}
                  onClick={() => onSelect(p.event)}
                  onContextMenu={(e) => { e.preventDefault(); onMenu(p.event, e.clientX, e.clientY); }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(p.event); }
                    else if (e.key === "Delete") { e.preventDefault(); onDelete(p.event); }
                    else if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
                      e.preventDefault();
                      const r = e.currentTarget.getBoundingClientRect();
                      onMenu(p.event, r.left + 20, r.top + 20);
                    }
                  }}>
                  <span className="acts">
                    {isOwn && <button className="a" aria-label={`Изменить «${p.event.name}»`} title="Изменить" onClick={(e) => { e.stopPropagation(); onEdit(p.event); }}><IconPencil /></button>}
                    {isOwn && <button className="a x" aria-label={`Удалить «${p.event.name}»`} title="Удалить" onClick={(e) => { e.stopPropagation(); onDelete(p.event); }}><IconClose /></button>}
                    <button className={`a bell${bell ? " on" : ""}`} aria-pressed={bell} aria-label={bell ? `Не напоминать о «${p.event.name}»` : `Напоминать о «${p.event.name}»`}
                      title={bell ? "Напоминание включено" : "Напомнить"} onClick={(e) => { e.stopPropagation(); schedule.toggleBell(p.event); }}><IconBell on={bell} /></button>
                  </span>
                  {tall ? (
                    <>
                      <b>{p.event.name}{isOwn && <span className="tag">своё</span>}</b>
                      <small>{shown(p.s, shift)}–{shown(p.e === 1440 ? 0 : p.e, shift)}</small>
                    </>
                  ) : p.lanes === 1 ? (
                    <><b className="one">{p.event.name}</b> <small className="inline">{shown(p.s, shift)}</small></>
                  ) : <b className="tiny">{p.event.name}</b>}
                </div>
              );
            })}
            {ghost && ghost.day === d.key && (
              <div className="sch-ghost" data-ghost style={{ top: yOf(ghost.s) + 1, height: yOf(ghost.e) - yOf(ghost.s) - 2 }}>
                Новое событие<small>{shown(ghost.s, shift)}–{shown(ghost.e === 1440 ? 0 : ghost.e, shift)}</small>
              </div>
            )}
            {isToday && <div className="sch-nowrow" style={{ top: yOf(nowMinute) }}><i /></div>}
          </div>
        );
      })}
    </div>
  );
}
