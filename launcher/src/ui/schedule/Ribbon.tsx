import { useEffect, useMemo, useRef, useState } from "react";

import { MINUTE } from "../../core/schedule/reminders";
import { Glide } from "../fx";
import { IconBell } from "../icons";
import { zoneShift } from "./Grid";
import { countdown, hm, occurrencesIn, Occurrence, ribbonLanes, toneOf } from "./layout";
import { bellKey } from "../../core/schedule/timing";
import type { Schedule } from "./useSchedule";

const HOUR = 60 * MINUTE;
const BACK = 3 * HOUR; // the ribbon starts 3 hours ago
const AHEAD = 24 * HOUR; // and goes 24 hours ahead
const VIEW_HOURS = 6; // the visible part is 6 hours: the focus; the rest is reached with the mouse wheel
const LEAD = 1 * HOUR; // «now» stands this far from the left edge of the visible part
const FOLLOW_AFTER_MS = 60_000; // after the user scrolled, the ribbon comes back to «now» when left alone this long

interface Props {
  schedule: Schedule;
  zone: "msk" | "local";
  onZone(zone: "msk" | "local"): void;
  onSelect(event: Occurrence["event"]): void;
}

/**
 * The ribbon: a clock, what comes next, and the events on a time line where an hour has one width everywhere. 6 hours
 * fill the view («now» an hour from its left edge); the line goes from 3 hours ago to 24 hours ahead and the mouse wheel
 * scrolls it. An event's box covers exactly its time, never another hour; a long name ends with «…».
 */
export function Ribbon({ schedule, zone, onZone, onSelect }: Props) {
  const { now } = schedule;
  const view = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800); // the visible width: VIEW_HOURS fit into it
  useEffect(() => {
    const el = view.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(el.clientWidth));
    observer.observe(el);
    setWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);
  const perHour = width / VIEW_HOURS;
  const start = now - BACK;
  const end = now + AHEAD;
  const at = (ms: number) => ((Math.max(start, Math.min(end, ms)) - start) / HOUR) * perHour; // px from the line's start
  const items = useMemo(() => occurrencesIn(schedule.visible, start, end), [schedule.visible, start, end]);
  const lanes = ribbonLanes(items); // only events that share time go one above the other
  const next = items.find((o) => o.start > now);
  const shift = zoneShift(zone);
  const clock = (ms: number) => hm((((Math.floor((ms % 86_400_000) / MINUTE) + shift) % 1440) + 1440) % 1440);
  const nowText = clock(now);
  const localText = hm((((Math.floor((now % 86_400_000) / MINUTE) + zoneShift("local")) % 1440) + 1440) % 1440);
  const ticks: number[] = [];
  for (let t = Math.ceil(start / HOUR) * HOUR; t <= end; t += HOUR) ticks.push(t);
  const laneCount = Math.max(1, ...lanes.map((l) => l + 1));
  const height = 24 + laneCount * 27;

  // the wheel scrolls the line; it follows «now» until the user scrolls, and again a minute after
  const touched = useRef(0);
  useEffect(() => {
    const el = view.current;
    if (!el) return;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      touched.current = Date.now();
      el.scrollLeft += Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
    };
    el.addEventListener("wheel", wheel, { passive: false });
    return () => el.removeEventListener("wheel", wheel);
  }, []);
  const follow = at(now) - (LEAD / HOUR) * perHour;
  useEffect(() => {
    const el = view.current;
    if (!el || Date.now() - touched.current < FOLLOW_AFTER_MS) return;
    el.scrollTo({ left: follow, behavior: touched.current ? "smooth" : "auto" });
  }, [follow]);

  return (
    <section className="sch-ribbon card" aria-label="Лента событий: 3 часа назад и сутки вперёд">
      <div className="rl">
        <div className="row">
          <div className="big">{nowText}<small>{zone === "msk" ? "МСК" : "у тебя"}</small></div>
          <div className="segmented small" role="radiogroup" aria-label="Какое время показывать">
            {([["msk", "МСК"], ["local", "Моё"]] as const).map(([value, label]) => (
              <button key={value} role="radio" aria-checked={zone === value} className={zone === value ? "on" : ""} onClick={() => onZone(value)}>{zone === value && <Glide group="seg-zone" />}<span>{label}</span></button>
            ))}
          </div>
        </div>
        <div className="muted small">{zone === "msk" ? `у тебя ${localText}` : "по времени этого компьютера"}</div>
        {next && (
          <div className="next">
            Дальше <b>{next.event.name}</b> в {clock(next.start)} · <span className="cd">через {countdown(next.start - now)}</span>
          </div>
        )}
      </div>
      <div className="rt" ref={view}>
        <div className="rt-track" style={{ width: at(end), minHeight: height }}>
          {ticks.map((t) => (
            <div key={t} className="tick" style={{ left: at(t) }}><span>{clock(t).slice(0, 2)}</span></div>
          ))}
          {items.map((o, i) => {
            const left = at(o.start);
            const past = o.end <= now;
            const long = o.end - o.start > 2 * HOUR;
            return (
              <button key={`${o.event.name}${o.start}`} className={`ev t-${toneOf(o.event)}${past ? " past" : ""}${o === next ? " nxt" : ""}`}
                style={{ left, width: Math.max(4, at(o.end) - left - 3), top: `calc(50% + 10px - ${(laneCount * 27) / 2}px + ${lanes[i] * 27}px)` }}
                title={`${o.event.name} ${clock(o.start)}–${clock(o.end)}`} onClick={() => onSelect(o.event)}>
                <span className="nm">{o.event.name}</span>{long && <span className="at"> {clock(o.start)}</span>}
                {schedule.bells.has(bellKey(o.event)) && <IconBell on />}
              </button>
            );
          })}
          <div className="nowline" style={{ left: at(now) }}><i /></div>
        </div>
      </div>
    </section>
  );
}
