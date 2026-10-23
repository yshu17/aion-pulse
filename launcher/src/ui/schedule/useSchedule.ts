import { useEffect, useMemo, useRef, useState } from "react";

import { Custom, eventKey, OWN_KIND } from "../../core/schedule/scheduleCustom";
import { ScheduleEvent } from "../../core/schedule/reminders";
import { bellKey, mskNow, parseEvents } from "../../core/schedule/timing";
import scheduleText from "../../../../data/schedule.json?raw";
import type { Boot } from "../useBoot";
import { slotOf, TONE_NAME, Tone } from "./layout";

export const CHIPS = ["Дерадиконы", "Арены", "Осады", "Прочее", "Своё"] as const;
export type Chip = (typeof CHIPS)[number];
export const CHIP_TONE: Record<Chip, Tone> = { "Дерадиконы": "blue", "Арены": "green", "Осады": "teal", "Прочее": "amber", "Своё": "purple" };
const STORED_GROUP: Record<Chip, string> = { "Дерадиконы": "Дерадиконы", "Арены": "Арены Хаоса и Доблести", "Осады": "Осады", "Прочее": "Прочее", "Своё": "Своё" };

/** The filter chip an event belongs to: own events together, the rest by the group of the data. */
export function chipOf(event: ScheduleEvent): Chip {
  if (event.kind === OWN_KIND) return "Своё";
  const group = String(event.group ?? "");
  if (group.startsWith("Дерадикон")) return "Дерадиконы";
  if (group.startsWith("Арен")) return "Арены";
  if (group.startsWith("Осад")) return "Осады";
  return "Прочее";
}

export interface Reset {
  name: string;
  when: string;
  day?: string;
  time: string;
}

/** What the form edits: the days an own event repeats on, with its time, name and group. */
export interface Draft {
  name: string;
  start: string;
  end: string;
  days: string[];
  chip: Chip;
  bell: boolean;
}

export interface Undo {
  label: string;
  snapshot: string;
}

const data = JSON.parse(scheduleText) as { events: ScheduleEvent[]; resets: Reset[] };
const base = parseEvents(scheduleText);
const COLOR_OF: Record<Chip, string> = { "Дерадиконы": TONE_NAME.blue, "Арены": TONE_NAME.green, "Осады": TONE_NAME.teal, "Прочее": TONE_NAME.amber, "Своё": TONE_NAME.purple };

const DEMO_OWN: ScheduleEvent[] = [
  { day: "thu", start: "18:00", end: "19:30", name: "Сбор легиона", group: "Своё", color: TONE_NAME.purple },
  { day: "fri", start: "18:00", end: "19:30", name: "Сбор легиона", group: "Своё", color: TONE_NAME.purple },
  { day: "sat", start: "12:00", end: "14:00", name: "Фарм Бездны", group: "Своё", color: TONE_NAME.purple },
];

const isSeries = (a: ScheduleEvent, b: ScheduleEvent) => a.name === b.name && a.start === b.start && a.end === b.end && a.group === b.group;

/** The schedule: the server's weekly events and the user's own ones (schedule_custom.json), filters and bells. */
export function useSchedule(boot: Boot) {
  const cfg = boot.config;
  const [now, setNow] = useState(() => mskNow());
  const [version, setVersion] = useState(0);
  const [undo, setUndo] = useState<Undo | null>(null);
  const custom = useRef<Custom>(Custom.load(null, null));
  const undoTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    const timer = setInterval(() => setNow(mskNow()), 30_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => { // own events from the file next to config.json; in a plain browser: a few made-up ones
    const files = boot.platform;
    const path = boot.ownFile("schedule_custom.json");
    if (files === null) {
      const demo = Custom.load(null, null);
      for (const event of DEMO_OWN) demo.add(event);
      custom.current = demo;
      setVersion((v) => v + 1);
      return;
    }
    if (!path) return;
    files.readText(path).then((text) => {
      custom.current = Custom.load(text, (out) => { files.writeText(path, out).catch(() => {}); });
      setVersion((v) => v + 1);
    });
  }, [boot.platform, boot.ownFile, boot.ready]);

  const events = useMemo(() => custom.current.merge(base).filter((e) => slotOf(e) !== null), [version]); // eslint-disable-line react-hooks/exhaustive-deps
  const hiddenGroups = useMemo(() => new Set(cfg.schedule_hidden), [cfg.schedule_hidden]);
  const visible = useMemo(() => events.filter((e) => !hiddenGroups.has(chipOf(e))), [events, hiddenGroups]);
  const counts = useMemo(() => {
    const out: Record<Chip, number> = { "Дерадиконы": 0, "Арены": 0, "Осады": 0, "Прочее": 0, "Своё": 0 };
    for (const e of events) out[chipOf(e)] += 1;
    return out;
  }, [events]);
  const bells = useMemo(() => new Set(cfg.remind_events), [cfg.remind_events]);

  const changed = () => setVersion((v) => v + 1);

  const remember = (label: string, before: string) => {
    clearTimeout(undoTimer.current);
    setUndo({ label, snapshot: before });
    undoTimer.current = setTimeout(() => setUndo(null), 6000);
  };
  const snapshot = () => JSON.stringify(custom.current.data);

  const toEvent = (draft: Draft, day: string): ScheduleEvent => ({
    day, start: draft.start, end: draft.end, name: draft.name.trim(), group: STORED_GROUP[draft.chip], color: COLOR_OF[draft.chip],
  });

  const api = {
    now, events, visible, counts, bells, version, undo, hiddenGroups,
    hiddenCount: custom.current.data.removed.length,
    resets: data.resets,
    isOwn: (e: ScheduleEvent) => e.kind === OWN_KIND,
    /** The days of the own events that repeat together with this one (same name, time and group). */
    seriesDays: (e: ScheduleEvent) => events.filter((x) => x.kind === OWN_KIND && isSeries(x, e)).map((x) => x.day),
    draftOf: (e: ScheduleEvent): Draft => ({
      name: e.name, start: e.start, end: e.end, chip: chipOf(e), bell: bells.has(bellKey(e)),
      days: events.filter((x) => x.kind === OWN_KIND && isSeries(x, e)).map((x) => x.day),
    }),
    toggleChip: (chip: Chip) => boot.save({ schedule_hidden: hiddenGroups.has(chip) ? cfg.schedule_hidden.filter((c) => c !== chip) : [...cfg.schedule_hidden, chip] }),
    toggleBell: (e: ScheduleEvent) => {
      const key = bellKey(e);
      boot.save({ remind_events: bells.has(key) ? cfg.remind_events.filter((k) => k !== key) : [...cfg.remind_events, key] });
    },
    create: (draft: Draft) => {
      for (const day of draft.days) custom.current.add(toEvent(draft, day));
      if (draft.bell) boot.save({ remind_events: [...new Set([...cfg.remind_events, ...draft.days.map((d) => bellKey(toEvent(draft, d)))])] });
      changed();
    },
    /** Replace a whole series of own events by the edited one. */
    update: (old: ScheduleEvent, draft: Draft) => {
      for (const day of api.seriesDays(old)) custom.current.remove({ ...old, day });
      api.create(draft);
    },
    /** One event: an own one is deleted, a server one is hidden. */
    removeOne: (e: ScheduleEvent) => {
      const before = snapshot();
      custom.current.remove(e);
      changed();
      remember(`${e.kind === OWN_KIND ? "Удалено" : "Скрыто"} «${e.name}»`, before);
    },
    removeSeries: (e: ScheduleEvent) => {
      const before = snapshot();
      for (const day of api.seriesDays(e)) custom.current.remove({ ...e, day });
      changed();
      remember(`Удалено «${e.name}», все повторы`, before);
    },
    restoreHidden: () => {
      custom.current.data.removed = [];
      custom.current.save();
      changed();
    },
    undoLast: () => {
      if (!undo) return;
      custom.current.data = JSON.parse(undo.snapshot);
      custom.current.save();
      clearTimeout(undoTimer.current);
      setUndo(null);
      changed();
    },
    keyOf: eventKey,
  };
  return api;
}

export type Schedule = ReturnType<typeof useSchedule>;
