/** What a buff, a scroll or a class skill of the gear calculator says in its tooltip: the stats it gives and how long it lasts. */

import type { Effect } from "./engine";
import { statName } from "./labels";

const fmt = (n: number) => Math.abs(n).toLocaleString("ru-RU", { maximumFractionDigits: 2 }).replace(/ /g, " ");

export function durationText(ms: number | undefined): string {
  if (!ms || ms < 1000) return "";
  const s = Math.round(ms / 1000), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return [h && `${h} ч`, m && `${m} мин`, sec && `${sec} с`].filter(Boolean).join(" ");
}

/** One line per stat (once each), «+» in front of a gain, «%» after a relative number; with `withTime` the longest duration last. */
export function effectLines(effects: Effect[], withTime = false): string[] {
  const out: string[] = [];
  let longest = 0;
  for (const e of effects) {
    if (e.type === "statup" && Array.isArray(e.stats)) {
      for (const s of e.stats as { name: string; value?: { value: number; relative?: boolean } }[]) {
        const v = s.value?.value;
        if (typeof v !== "number") continue;
        const line = `${statName(s.name)} ${v < 0 ? "−" : "+"}${fmt(v)}${s.value?.relative ? "%" : ""}`;
        if (!out.includes(line)) out.push(line);
      }
      longest = Math.max(longest, Number(e.remain_time) || 0);
    } else if (e.type === "heal_instant" && typeof e.value?.value === "number") {
      const line = `Мгновенное лечение ${fmt(e.value.value)}${e.value.relative ? "%" : ""}`;
      if (!out.includes(line)) out.push(line);
    }
  }
  const time = withTime ? durationText(longest) : "";
  return time ? [...out, `Длительность: ${time}`] : out;
}

/**
 * The tooltip's corner by the pointer: `gap` below and to the right of it, turned to the left near the right edge and
 * above near the bottom, and kept `margin` inside the window when the box is bigger than the room on either side.
 */
export function tipPlace(cursor: [number, number], size: [number, number], view: [number, number], gap = 14, margin = 8): { x: number; y: number } {
  const along = (at: number, len: number, room: number) => {
    let pos = at + gap;
    if (pos + len > room - margin) pos = at - gap - len;
    return Math.max(margin, Math.min(pos, room - margin - len));
  };
  return { x: along(cursor[0], size[0], view[0]), y: along(cursor[1], size[1], view[1]) };
}
