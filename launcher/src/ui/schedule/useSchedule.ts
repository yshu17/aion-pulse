import { useEffect, useMemo, useRef, useState } from "react";

import { ReminderPlanner } from "../../core/schedule/reminderFlow";
import { Custom, eventKey, OWN_KIND } from "../../core/schedule/scheduleCustom";
import { ScheduleEvent } from "../../core/schedule/reminders";
import { ARTICLE, decide, knownFingerprint, siteFingerprint } from "../../core/schedule/scheduleUpdate";
import { bellKey, mskNow, parseEvents } from "../../core/schedule/timing";
import scheduleText from "../../../../data/schedule.json?raw";
import type { Boot } from "../useBoot";
import { countdown, slotOf, TONE_NAME, Tone } from "./layout";

export const CHIPS = ["Дерадиконы", "Арены", "Осады", "Прочее", "Своё"] as const;
export type Chip = (typeof CHIPS)[number];
export const CHIP_TONE: Record<Chip, Tone> = { "Дерадиконы": "blue", "Арены": "green", "Осады": "teal", "Прочее": "amber", "Своё": "purple" };
const STORED_GROUP: Record<Chip, string> = { "Дерадиконы": "Дерадиконы", "Арены": "Арены Хаоса и Доблести", "Осады": "Осады", "Прочее": "Прочее", "Своё": "Своё" };

/** The filter chip an event belongs to: own events together, the rest by the group of the data. */
export function chipOf(event: ScheduleEvent): Chip {
  if (event.kind === OWN_KIND && (!event.group || event.group === "Своё")) return "Своё";
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

/** What the form edits: the days an event repeats on, with its time, name, group and reminder. */
export interface Draft {
  name: string;
  start: string;
  end: string;
  days: string[];
  chip: Chip;
  bell: boolean;
  lead: number; // minutes before the start the reminder comes
}

/** The answer of «Проверить обновление»: is the picture on the knowledge base still the one the grid was typed from? */
export interface SiteCheck {
  state: "busy" | "same" | "changed" | "error";
  text: string;
}

export interface Undo {
  label: string;
  snapshot: string;
  until: number; // Date.now() when «Отменить удаление» goes away
}

const data = JSON.parse(scheduleText) as { events: ScheduleEvent[]; resets: Reset[] };
const base = parseEvents(scheduleText);
const COLOR_OF: Record<Chip, string> = { "Дерадиконы": TONE_NAME.blue, "Арены": TONE_NAME.green, "Осады": TONE_NAME.teal, "Прочее": TONE_NAME.amber, "Своё": TONE_NAME.purple };
const KNOWN = knownFingerprint(data as unknown as Record<string, unknown>);
const LEADS_FILE = "schedule_leads.json"; // next to config.json: {"<bell key>": minutes} for events with their own lead
const REMIND_EVERY_MS = 20_000;
export const UNDO_MS = 30_000; // how long a deleted event can be brought back

const DEMO_OWN: ScheduleEvent[] = [
  { day: "thu", start: "18:00", end: "19:30", name: "Сбор легиона", group: "Своё", color: TONE_NAME.purple },
  { day: "fri", start: "18:00", end: "19:30", name: "Сбор легиона", group: "Своё", color: TONE_NAME.purple },
  { day: "sat", start: "12:00", end: "14:00", name: "Фарм Бездны", group: "Своё", color: TONE_NAME.purple },
];

const isSeries = (a: ScheduleEvent, b: ScheduleEvent) => a.name === b.name && a.start === b.start && a.end === b.end && a.group === b.group;

/** The schedule: server events and own ones (schedule_custom.json), filters, bells and reminders with their leads. */
export function useSchedule(boot: Boot, notify: (title: string, text: string) => void) {
  const cfg = boot.config;
  const [now, setNow] = useState(() => mskNow());
  const [version, setVersion] = useState(0);
  const [undo, setUndo] = useState<Undo | null>(null);
  const [leads, setLeads] = useState<Record<string, number>>({});
  const [site, setSite] = useState<SiteCheck | null>(null);
  const custom = useRef<Custom>(Custom.load(null, null));
  const undoTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const planner = useRef(new ReminderPlanner());
  const notifyRef = useRef(notify);
  notifyRef.current = notify;

  useEffect(() => {
    const timer = setInterval(() => setNow(mskNow()), 30_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => { // own events and leads from the files next to config.json; in a plain browser: a few made-up ones
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
    files.readText(boot.ownFile(LEADS_FILE)).then((text) => {
      try {
        const clean: Record<string, number> = {};
        for (const [key, value] of Object.entries(text ? JSON.parse(text) : {})) {
          if (Number.isInteger(value) && (value as number) > 0) clean[key] = value as number;
        }
        setLeads(clean);
      } catch { /* a broken file: every event uses the common lead */ }
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
  const leadOf = (e: ScheduleEvent) => leads[bellKey(e)] ?? cfg.remind_min;

  useEffect(() => { // reminders of belled events, each with its own lead, on every tab
    const belled = events.filter((e) => bells.has(bellKey(e)));
    if (!belled.length) return;
    const check = () => {
      const byLead = new Map<number, ScheduleEvent[]>();
      for (const e of belled) {
        const lead = leads[bellKey(e)] ?? cfg.remind_min;
        byLead.set(lead, [...(byLead.get(lead) ?? []), e]);
      }
      const at = mskNow();
      for (const [lead, group] of byLead) {
        for (const r of planner.current.due(group, at, lead)) { // the real time left, and whose event it is
          const title = r.title.startsWith("Через") ? `Через ${countdown(r.start - at + 59_999)}: ${r.event.name}` : r.title;
          notifyRef.current(title, r.text.replace("расписание сервера", r.event.kind === OWN_KIND ? "своё событие" : "расписание сервера"));
        }
      }
    };
    check();
    const timer = setInterval(check, REMIND_EVERY_MS);
    return () => clearInterval(timer);
  }, [events, bells, leads, cfg.remind_min]);

  /** Ask the knowledge base; a manual check always answers on the tab, the check at start only reports a new version. */
  const checkSite = async (manual: boolean) => {
    const files = boot.platform;
    if (files === null) {
      if (manual) setSite({ state: "error", text: "Проверка работает только в программе, не в браузере." });
      return;
    }
    if (manual) setSite({ state: "busy", text: "Проверяю…" });
    try {
      const current = await siteFingerprint((url, method) => files.httpFetch(url, method));
      const verdict = decide(KNOWN, current, cfg.schedule_seen, manual);
      if (verdict === "changed") {
        boot.save({ schedule_seen: current }); // said once: the check at start keeps quiet about this version
        if (manual) setSite({ state: "changed", text: "Расписание на сайте обновилось: сверь сетку со статьёй." });
        else notifyRef.current("Расписание на сайте обновилось", "Картинка в базе знаний новая: сверь сетку, вкладка «Расписание».");
      } else if (verdict === "same") {
        setSite({ state: "same", text: "Расписание актуально: картинка на сайте та же." });
      }
    } catch (error) {
      if (manual) setSite({ state: "error", text: `Не удалось проверить: ${String(error).slice(0, 120)}` });
    }
  };
  const checkedAtStart = useRef(false);
  useEffect(() => { // once, a few seconds after the start, when the setting allows
    if (!boot.ready || boot.platform === null || checkedAtStart.current || !cfg.schedule_check) return;
    checkedAtStart.current = true;
    const timer = setTimeout(() => { checkSite(false); }, 5000);
    return () => clearTimeout(timer);
  }, [boot.ready]); // eslint-disable-line react-hooks/exhaustive-deps

  const changed = () => setVersion((v) => v + 1);

  const saveLeads = (next: Record<string, number>) => {
    setLeads(next);
    const files = boot.platform;
    const path = boot.ownFile(LEADS_FILE);
    if (files && path) files.writeText(path, JSON.stringify(next, null, 1) + "\n").catch(() => {});
  };

  const remember = (label: string, before: string) => {
    clearTimeout(undoTimer.current);
    setUndo({ label, snapshot: before, until: Date.now() + UNDO_MS });
    undoTimer.current = setTimeout(() => setUndo(null), UNDO_MS);
  };
  const snapshot = () => JSON.stringify(custom.current.data);

  const toEvent = (draft: Draft, day: string): ScheduleEvent => ({
    day, start: draft.start, end: draft.end, name: draft.name.trim(), group: STORED_GROUP[draft.chip], color: COLOR_OF[draft.chip],
  });

  /** Forget the bells and leads of `drop`, then set them for the draft's days as the draft says (one save). */
  const setReminders = (drop: string[], draft: Draft) => {
    const keys = draft.days.map((d) => bellKey(toEvent(draft, d)));
    const kept = cfg.remind_events.filter((k) => !drop.includes(k) && !keys.includes(k));
    boot.save({ remind_events: draft.bell ? [...kept, ...keys] : kept });
    const next = { ...leads };
    for (const k of [...drop, ...keys]) delete next[k];
    if (draft.bell && draft.lead !== cfg.remind_min) for (const k of keys) next[k] = draft.lead;
    saveLeads(next);
  };

  /** An own event with its repeats (same name, time and group); a server event alone. */
  const seriesOf = (e: ScheduleEvent) => (e.kind === OWN_KIND ? events.filter((x) => x.kind === OWN_KIND && isSeries(x, e)) : [e]);

  const api = {
    now, events, visible, counts, bells, version, undo, hiddenGroups, leadOf, defaultLead: cfg.remind_min,
    hiddenCount: custom.current.data.removed.length,
    resets: data.resets,
    /** Made by the user from scratch (a server event the user edited keeps its own look and group). */
    isOwn: (e: ScheduleEvent) => e.kind === OWN_KIND && chipOf(e) === "Своё",
    /** A server event the user changed: an own copy in its place. */
    isEdited: (e: ScheduleEvent) => e.kind === OWN_KIND && chipOf(e) !== "Своё",
    seriesDays: (e: ScheduleEvent) => seriesOf(e).map((x) => x.day),
    draftOf: (e: ScheduleEvent): Draft => ({
      name: e.name, start: e.start, end: e.end, chip: chipOf(e), bell: bells.has(bellKey(e)), lead: leadOf(e),
      days: seriesOf(e).map((x) => x.day),
    }),
    toggleChip: (chip: Chip) => boot.save({ schedule_hidden: hiddenGroups.has(chip) ? cfg.schedule_hidden.filter((c) => c !== chip) : [...cfg.schedule_hidden, chip] }),
    toggleBell: (e: ScheduleEvent) => {
      const key = bellKey(e);
      boot.save({ remind_events: bells.has(key) ? cfg.remind_events.filter((k) => k !== key) : [...cfg.remind_events, key] });
    },
    /** Minutes before the start this event's reminder comes; the common lead of the settings is not stored per event. */
    setLead: (e: ScheduleEvent, minutes: number) => {
      const next = { ...leads };
      if (minutes === cfg.remind_min) delete next[bellKey(e)];
      else next[bellKey(e)] = minutes;
      saveLeads(next);
    },
    create: (draft: Draft) => {
      for (const day of draft.days) custom.current.add(toEvent(draft, day));
      setReminders([], draft);
      changed();
    },
    /** Replace an own event with all its repeats, or put an own copy in place of a server event (the original is hidden). */
    update: (old: ScheduleEvent, draft: Draft) => {
      const series = seriesOf(old);
      for (const e of series) custom.current.remove(e);
      for (const day of draft.days) custom.current.add(toEvent(draft, day));
      setReminders(series.map(bellKey), draft);
      changed();
    },
    /** One event: an own one is deleted, a server one is hidden. */
    removeOne: (e: ScheduleEvent) => {
      const before = snapshot();
      custom.current.remove(e);
      changed();
      remember(`Удалено «${e.name}»`, before);
    },
    removeSeries: (e: ScheduleEvent) => {
      const before = snapshot();
      for (const x of seriesOf(e)) custom.current.remove(x);
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
    site,
    checkSite: () => checkSite(true),
    openArticle: () => { boot.platform?.openUrl(ARTICLE).catch(() => {}); if (boot.platform === null) window.open(ARTICLE, "_blank"); },
  };
  return api;
}

export type Schedule = ReturnType<typeof useSchedule>;
