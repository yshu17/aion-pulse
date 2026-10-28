import { useEffect, useMemo, useRef, useState } from "react";

import { MINUTE } from "../../core/schedule/reminders";
import { Glide } from "../fx";
import { IconBell } from "../icons";
import { zoneShift } from "./Grid";
import { countdown, hm, occurrencesIn, Occurrence, ribbonLanes, toneOf } from "./layout";
import { bellKey, mskNow } from "../../core/schedule/timing";
import type { Schedule } from "./useSchedule";

const HOUR = 60 * MINUTE;
const BACK_HOURS = 3; // the line starts 3 whole hours before the current hour
const AHEAD = 24 * HOUR; // and goes 24 hours ahead
const VIEW_HOURS = 6; // the visible part is 6 hours: the focus; the rest is reached with the mouse wheel, an hour a notch
const LEAD_HOURS = 2; // the view starts 2 hours before the current hour: the event of an hour ago is seen whole, «now» near the middle
const FOLLOW_AFTER_MS = 60_000; // after the user scrolled, the ribbon comes back to «now» when left alone this long

interface Props {
  schedule: Schedule;
  zone: "msk" | "local";
  onZone(zone: "msk" | "local"): void;
  onSelect(event: Occurrence["event"]): void;
}

/**
 * The ribbon: a clock, what comes next, and the events on a time line where an hour has one width everywhere. 6 whole
 * hours fill the view, from 2 hours before the current one: «now» walks through its hour near the middle, and when the
 * hour is over the view moves on by one. The mouse wheel moves it an hour a notch (3 hours back, 24 ahead). An event's
 * box covers exactly its time, never another hour; a long name ends with «…».
 */
export function Ribbon({ schedule, zone, onZone, onSelect }: Props) {
  const { now } = schedule;
  const [live, setLive] = useState(() => mskNow()); // the time to the second: the «now» line and its label move with it
  useEffect(() => {
    const timer = setInterval(() => setLive(mskNow()), 1000);
    return () => clearInterval(timer);
  }, []);
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
  const hour = Math.floor(now / HOUR) * HOUR; // the current whole hour
  const start = hour - BACK_HOURS * HOUR;
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

  // the view's first hour (counted from the line's start); the wheel moves it one hour a notch, and it follows the
  // current hour until the user scrolls, and again a minute after
  const home = BACK_HOURS - LEAD_HOURS;
  const lastFirst = BACK_HOURS + AHEAD / HOUR - VIEW_HOURS;
  const [first, setFirst] = useState(home);
  const touched = useRef(0);
  const firstRef = useRef(first);
  firstRef.current = first;
  useEffect(() => {
    const el = view.current;
    if (!el) return;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      if (delta === 0) return;
      touched.current = Date.now();
      setFirst(Math.min(lastFirst, Math.max(0, firstRef.current + Math.sign(delta))));
    };
    el.addEventListener("wheel", wheel, { passive: false });
    return () => el.removeEventListener("wheel", wheel);
  }, [lastFirst]);
  useEffect(() => { // a new hour (or back from scrolling): the view goes home
    if (Date.now() - touched.current >= FOLLOW_AFTER_MS) setFirst(home);
    const timer = setInterval(() => { if (touched.current && Date.now() - touched.current >= FOLLOW_AFTER_MS) { touched.current = 0; setFirst(home); } }, 5000);
    return () => clearInterval(timer);
  }, [hour, home]);
  useEffect(() => { // whole hours: the view's left edge is always on an hour
    view.current?.scrollTo({ left: first * perHour, behavior: touched.current ? "smooth" : "auto" });
  }, [first, perHour]);

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
            <div key={t} className="tick" style={{ left: at(t) }}><span>{clock(t)}</span></div>
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
          <div className="nowline" style={{ left: at(live) }}><i /><b className="now-t num">{clock(live)}:{String(Math.floor(live / 1000) % 60).padStart(2, "0")}</b></div>
        </div>
      </div>
    </section>
  );
}
