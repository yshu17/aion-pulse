import { useEffect, useMemo, useRef, useState } from "react";

import { dayStart, ScheduleEvent } from "../../core/schedule/reminders";
import type { Reset } from "../../core/schedule/resets";
import { bellKey, localZone, MSK_OFFSET } from "../../core/schedule/timing";
import { IconBell, IconClose, IconPencil } from "../icons";
import { Axis, buildAxis, cardFont, cardNeed, fitName, Measure, hm, minuteAt, Placed, placeDay, toMinutes, toneOf, yOf } from "./layout";
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
const LABEL_GAP = 16; // hour labels closer than this to the one above are left out
const CHIP_PX = { char: 6, pad: 14, gap: 3, row: 18 }; // a reset chip: 11 px text, its padding and border

/** How tall the chips of resets are when they wrap in a column of this width. */
function chipsHeight(labels: string[], width: number): number {
  let rows = 1;
  let used = 0;
  for (const label of labels) {
    const w = label.length * CHIP_PX.char + CHIP_PX.pad;
    if (used > 0 && used + CHIP_PX.gap + w > width) { rows += 1; used = w; } else used += (used > 0 ? CHIP_PX.gap : 0) + w;
  }
  return rows * CHIP_PX.row + (rows - 1) * CHIP_PX.gap + 8;
}

/** The hour lines and labels of the shown hours: every hour start, and the end of the day when it is shown. */
function hourMarks(axis: Axis): number[] {
  const out: number[] = [];
  for (const b of axis.bands) if (b.kind === "hours") for (let m = b.from; m <= b.to; m += 60) if (!out.includes(m)) out.push(m);
  return out;
}

/** The width of a card title at a font size, as the screen draws it. */
const ctx = document.createElement("canvas").getContext("2d");
const measure: Measure = (text, size) => {
  if (!ctx) return text.length * size * 0.57;
  ctx.font = `600 ${size}px "Segoe UI", system-ui, sans-serif`;
  return ctx.measureText(text).width;
};

/** The hour band a reset is drawn in. */
const resetHour = (r: Reset) => Math.floor(toMinutes(r.time) / 60) * 60;

/** Minutes to add to an MSK time of day to show it on this computer's clock. */
/** The short mark of a reset in the folded night: the usual three by their kind, a renamed or own one by its name. */
function resetLabel(r: Reset): string {
  if (r.own || r.edited) return r.name;
  if (r.days.length === 7) return "Откат";
  return r.name.includes("БП") ? "+ БП" : "+ неделя";
}

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
  const root = useRef<HTMLDivElement>(null);
  const [colW, setColW] = useState(120); // the width of a day column: how much room the card text has
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const measure = () => { const col = el.querySelector<HTMLElement>(".sch-col"); if (col) setColW(col.clientWidth); };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [days.length]);

  // what each day shows, then one axis for all of them: the hours with events, the resets, the rest folded
  const columns = useMemo(() => days.map((d) => ({
    day: d,
    placed: placeDay(schedule.visible.filter((e) => e.day === d.key)),
    resets: schedule.resets.filter((r) => r.days.includes(d.key)),
  })), [days, schedule.visible, schedule.resets]);
  const axis = useMemo(() => {
    const spans = columns.flatMap((c) => c.placed.map((p: Placed) => ({ s: p.s, e: p.e, px: cardNeed(p.event.name, colW / p.lanes, measure) })));
    const byHour = new Map<number, number>();
    for (const c of columns) {
      const groups = new Map<number, string[]>();
      for (const r of c.resets) groups.set(resetHour(r), [...(groups.get(resetHour(r)) ?? []), resetLabel(r)]);
      for (const [at, labels] of groups) byHour.set(at, Math.max(byHour.get(at) ?? 0, chipsHeight(labels, colW - 8)));
    }
    return buildAxis({ spans, resets: [...byHour].map(([minute, px]) => ({ minute, px })) });
  }, [columns, colW]);
  const marks = hourMarks(axis);
  const today = dayStart(now);
  const nowMinute = Math.floor((now - today) / 60000);
  const shift = zoneShift(zone);
  const drag = useRef<{ day: string; from: number; rect: DOMRect } | null>(null);

  const down = (e: React.PointerEvent<HTMLDivElement>, day: string) => {
    if (e.button !== 0 || (e.target as HTMLElement).closest(".sch-card, .sch-ghost")) return; // only on an empty place
    const rect = e.currentTarget.getBoundingClientRect();
    const minute = minuteAt(axis, e.clientY - rect.top);
    if (minute === null) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { day, from: minute, rect };
    onGhost({ day, s: minute, e: Math.min(1440, minute + 60) }, false);
  };
  const move = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d) return;
    const minute = minuteAt(axis, Math.min(axis.height, Math.max(0, e.clientY - d.rect.top)));
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
    <div className="sch-grid card" ref={root} style={{ ["--n" as string]: days.length }}>
      <div />
      {days.map((d) => (
        <div key={d.key + d.date} className={`sch-dh${d.date === today ? " today" : ""}`}>
          {DAY_SHORT[d.key]} <b>{new Date(d.date).getUTCDate()}</b>
        </div>
      ))}

      <div className="sch-axis" style={{ height: axis.height }} aria-hidden>
        {(() => {
          const nowY = days.some((d) => d.date === today) ? yOf(axis, nowMinute) : null;
          let last = -Infinity;
          return marks.map((m) => {
            const y = yOf(axis, m, m === 1440);
            if (y - last < LABEL_GAP || (nowY !== null && Math.abs(y - nowY) < LABEL_GAP)) return null;
            last = y;
            return <span key={m} style={{ top: y }}>{shown(m, shift)}</span>;
          });
        })()}
        {days.some((d) => d.date === today) && <span className="nowchip" style={{ top: yOf(axis, nowMinute) }}>{shown(nowMinute, shift)}</span>}
      </div>

      {columns.map(({ day: d, placed, resets }) => {
        const isToday = d.date === today;
        return (
          <div key={d.key + d.date} className={`sch-col${isToday ? " today" : ""}`} style={{ height: axis.height }}
            onPointerDown={(e) => down(e, d.key)} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
            {marks.map((m) => <div key={m} className="sch-hl" style={{ top: yOf(axis, m, m === 1440) }} />)}
            {axis.bands.filter((b) => b.kind !== "hours").map((b) => (
              <div key={b.kind + b.from} className={`sch-fold${b.kind === "resets" ? " resets" : ""}`} style={{ top: b.y, height: b.h }}>
                {b.kind === "resets" && (
                  <div className="sch-resets">
                    {resets.filter((r) => resetHour(r) === b.from).map((r) => (
                      <span key={r.id} className={schedule.resetBells.has(r.id) ? "belled" : ""} title={`${r.name} в ${r.time} МСК${schedule.resetBells.has(r.id) ? ", напомню" : ""}`}>
                        {resetLabel(r)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {placed.map((p) => {
              const top = yOf(axis, p.s) + 1;
              const height = yOf(axis, p.e, true) - top - 1;
              const width = 100 / p.lanes;
              const past = d.date + p.e * 60000 <= now;
              const isOwn = schedule.isOwn(p.event);
              const isSel = selected !== null && schedule.keyOf(selected) === schedule.keyOf(p.event);
              const bell = schedule.bells.has(bellKey(p.event));
              const font = cardFont(p.event.name, colW / p.lanes, measure);
              const label = `${p.event.name}, ${DAY_SHORT[d.key]} ${shown(p.s, shift)}–${shown(p.e === 1440 ? 0 : p.e, shift)}`;
              return (
                <div key={schedule.keyOf(p.event)} className={`sch-card t-${toneOf(p.event)}${past ? " past" : ""}${isOwn ? " own" : ""}${isSel ? " sel" : ""}${bell ? " belled" : ""}`}
                  style={{ top, height, left: `calc(${p.lane * width}% + 2px)`, width: `calc(${width}% - 4px)`, fontSize: font }}
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
                    <button className="a" aria-label={`Изменить «${p.event.name}»`} title="Изменить" onClick={(e) => { e.stopPropagation(); onEdit(p.event); }}><IconPencil /></button>
                    <button className="a x" aria-label={`Удалить «${p.event.name}»`} title="Удалить" onClick={(e) => { e.stopPropagation(); onDelete(p.event); }}><IconClose /></button>
                    <button className={`a bell${bell ? " on" : ""}`} aria-pressed={bell} aria-label={bell ? `Не напоминать о «${p.event.name}»` : `Напоминать о «${p.event.name}»`}
                      title={bell ? "Напоминание включено" : "Напомнить"} onClick={(e) => { e.stopPropagation(); schedule.toggleBell(p.event); }}><IconBell on={bell} /></button>
                  </span>
                  <b>{fitName(p.event.name, colW / p.lanes, (text) => measure(text, font))}</b>
                  <small>{shown(p.s, shift)}–<wbr />{shown(p.e === 1440 ? 0 : p.e, shift)}</small>
                </div>
              );
            })}
            {ghost && ghost.day === d.key && (
              <div className="sch-ghost" data-ghost style={{ top: yOf(axis, ghost.s) + 1, height: yOf(axis, ghost.e, true) - yOf(axis, ghost.s) - 2 }}>
                Новое событие<small>{shown(ghost.s, shift)}–{shown(ghost.e === 1440 ? 0 : ghost.e, shift)}</small>
              </div>
            )}
            {isToday && <div className="sch-nowrow" style={{ top: yOf(axis, nowMinute) }}><i /></div>}
          </div>
        );
      })}
    </div>
  );
}
