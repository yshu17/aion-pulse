import { useMemo } from "react";

import { MINUTE } from "../../core/schedule/reminders";
import { IconBell } from "../icons";
import { zoneShift } from "./Grid";
import { countdown, hm, occurrencesIn, Occurrence, ribbonLanes, toneOf } from "./layout";
import { bellKey } from "../../core/schedule/timing";
import type { Schedule } from "./useSchedule";

const SPAN = 24 * 60 * MINUTE;
const BEFORE = 60 * MINUTE;

interface Props {
  schedule: Schedule;
  zone: "msk" | "local";
  onZone(zone: "msk" | "local"): void;
  onSelect(event: Occurrence["event"]): void;
}

/** «Now and the next 24 hours»: a clock, what comes next, and the events on a line with the NOW marker. */
export function Ribbon({ schedule, zone, onZone, onSelect }: Props) {
  const { now } = schedule;
  const start = now - BEFORE;
  const items = useMemo(() => occurrencesIn(schedule.visible, start, start + SPAN), [schedule.visible, start]);
  const lanes = ribbonLanes(items);
  const next = items.find((o) => o.start > now);
  const shift = zoneShift(zone);
  const clock = (ms: number) => hm((((Math.floor((ms % 86_400_000) / MINUTE) + shift) % 1440) + 1440) % 1440);
  const nowText = clock(now);
  const localText = hm((((Math.floor((now % 86_400_000) / MINUTE) + zoneShift("local")) % 1440) + 1440) % 1440);
  const firstHour = Math.ceil(start / (60 * MINUTE)) * 60 * MINUTE;
  const ticks: number[] = [];
  for (let t = firstHour; t < start + SPAN; t += 120 * MINUTE) ticks.push(t);
  const laneCount = Math.max(1, ...lanes.map((l) => l + 1));
  const height = 24 + laneCount * 27;

  return (
    <section className="sch-ribbon card" aria-label="Сейчас и ближайшие 24 часа">
      <div className="rl">
        <div className="row">
          <div className="big">{nowText}<small>{zone === "msk" ? "МСК" : "у тебя"}</small></div>
          <div className="segmented small" role="radiogroup" aria-label="Какое время показывать">
            {([["msk", "МСК"], ["local", "Моё"]] as const).map(([value, label]) => (
              <button key={value} role="radio" aria-checked={zone === value} className={zone === value ? "on" : ""} onClick={() => onZone(value)}>{label}</button>
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
      <div className="rt" style={{ minHeight: height }}>
        {ticks.map((t) => (
          <div key={t} className="tick" style={{ left: `${((t - start) / SPAN) * 100}%` }}><span>{clock(t).slice(0, 2)}</span></div>
        ))}
        {items.map((o, i) => {
          const left = Math.max(0, (o.start - start) / SPAN) * 100;
          const right = Math.min(1, (o.end - start) / SPAN) * 100;
          const past = o.end <= now;
          const long = o.end - o.start > 120 * MINUTE;
          return (
            <button key={`${o.event.name}${o.start}`} className={`ev t-${toneOf(o.event)}${past ? " past" : ""}${o === next ? " nxt" : ""}`}
              style={{ left: `${left}%`, width: `calc(${right - left}% - 3px)`, top: `calc(50% + 10px - ${(laneCount * 27) / 2}px + ${lanes[i] * 27}px)` }}
              title={`${o.event.name} ${clock(o.start)}–${clock(o.end)}`} onClick={() => onSelect(o.event)}>
              {o.event.name}{long && <span className="at"> {clock(o.start)}</span>}
              {schedule.bells.has(bellKey(o.event)) && <IconBell on />}
            </button>
          );
        })}
        <div className="nowline" style={{ left: `${(BEFORE / SPAN) * 100}%` }}><i /></div>
      </div>
    </section>
  );
}
