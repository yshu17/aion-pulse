import { useEffect, useMemo, useRef, useState } from "react";

import { MINUTE } from "../../core/schedule/reminders";
import { Glide } from "../fx";
import { IconBell } from "../icons";
import { zoneShift } from "./Grid";
import { countdown, hm, occurrencesIn, Occurrence, RIBBON_FOCUS, RIBBON_HALF, packLanes, ribbonX, toneOf } from "./layout";
import { bellKey } from "../../core/schedule/timing";
import type { Schedule } from "./useSchedule";


/** The width of an event's name on the ribbon (semibold, 12 px near now, 10 px far away), as the screen draws it. */
const ctx = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
function measure(text: string, size: number): number {
  if (!ctx) return text.length * size * 0.6;
  ctx.font = `600 ${size}px "Segoe UI", system-ui, sans-serif`;
  return Math.ceil(ctx.measureText(text).width);
}

interface Props {
  schedule: Schedule;
  zone: "msk" | "local";
  onZone(zone: "msk" | "local"): void;
  onSelect(event: Occurrence["event"]): void;
}

/**
 * «Now» in the middle of 24 hours (12 before, 12 after): a clock, what comes next, and the events sliding past the NOW
 * marker. The ribbon is a magnifier: the hours near now are wide and their events full size, the far ones small.
 */
export function Ribbon({ schedule, zone, onZone, onSelect }: Props) {
  const { now } = schedule;
  const start = now - RIBBON_HALF;
  const items = useMemo(() => occurrencesIn(schedule.visible, start, now + RIBBON_HALF), [schedule.visible, start, now]);
  const next = items.find((o) => o.start > now);
  const shift = zoneShift(zone);
  const clock = (ms: number) => hm((((Math.floor((ms % 86_400_000) / MINUTE) + shift) % 1440) + 1440) % 1440);
  const nowText = clock(now);
  const localText = hm((((Math.floor((now % 86_400_000) / MINUTE) + zoneShift("local")) % 1440) + 1440) % 1440);
  const firstHour = Math.ceil(start / (60 * MINUTE)) * 60 * MINUTE;
  const ticks: number[] = []; // every hour near now, every second hour further away
  for (let t = firstHour; t < now + RIBBON_HALF; t += 60 * MINUTE) {
    if (Math.abs(t - now) <= RIBBON_FOCUS || Math.round(t / (60 * MINUTE)) % 2 === 0) ticks.push(t);
  }
  const at = (ms: number) => ribbonX(ms - now) * 100; // percent of the width
  const line = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800); // the ribbon's width: how much room a short event has for its name
  useEffect(() => {
    const el = line.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(el.clientWidth));
    observer.observe(el);
    setWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);
  // each event is at least as wide as its name; events that would then touch go one above the other
  const boxes = items.map((o) => {
    const far = o.end < now - RIBBON_FOCUS || o.start > now + RIBBON_FOCUS;
    const long = o.end - o.start > 120 * MINUTE;
    const text = o.event.name + (long ? ` ${clock(o.start)}` : "");
    const need = measure(text, far ? 10 : 12) + (far ? 15 : 21) + (schedule.bells.has(bellKey(o.event)) ? 16 : 0);
    const from = (at(o.start) / 100) * width;
    const to = Math.max((at(o.end) / 100) * width, from + need);
    return { from, to, far, long };
  });
  const lanes = packLanes(boxes, 3);
  const laneCount = Math.max(1, ...lanes.map((l) => l + 1));
  const height = 24 + laneCount * 27;

  return (
    <section className="sch-ribbon card" aria-label="12 часов до и после текущего момента">
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
      <div className="rt" ref={line} style={{ minHeight: height }}>
        {ticks.map((t) => (
          <div key={t} className="tick" style={{ left: `${at(t)}%` }}><span>{clock(t).slice(0, 2)}</span></div>
        ))}
        {items.map((o, i) => {
          const { from, to, far, long } = boxes[i]; // far: all of it outside the magnified hours
          const past = o.end <= now;
          return (
            <button key={`${o.event.name}${o.start}`} className={`ev t-${toneOf(o.event)}${past ? " past" : ""}${far ? " far" : ""}${o === next ? " nxt" : ""}`}
              style={{ left: from, width: to - from - 3, top: `calc(50% + 10px - ${(laneCount * 27) / 2}px + ${lanes[i] * 27}px)` }}
              title={`${o.event.name} ${clock(o.start)}–${clock(o.end)}`} onClick={() => onSelect(o.event)}>
              {o.event.name}{long && <span className="at"> {clock(o.start)}</span>}
              {schedule.bells.has(bellKey(o.event)) && <IconBell on />}
            </button>
          );
        })}
        <div className="nowline" style={{ left: "50%" }}><i /></div>
      </div>
    </section>
  );
}
