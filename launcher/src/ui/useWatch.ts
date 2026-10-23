import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { LOUD, WatchSession } from "../core/chat/session";
import { naiveMs } from "../core/chat/tailer";
import { AlertBridge } from "../core/notify/bridge";
import { Notification, NotificationCenter } from "../core/notify/center";
import { demoLine, itemById, itemNames, mapNames, questNames, watchItems } from "./data";
import { FeedRow, makeRows } from "./chatRows";
import { AsyncLogFeed } from "./logFeed";
import { makeSound } from "./sound";
import type { Boot } from "./useBoot";

export type AlertState = "accepted" | "missed";

export interface Toast {
  note: Notification;
  icon: string | null;
}

/** Where the lines come from: demo lines in a browser, Chat.log in the program, or why there are none. */
export interface Source {
  kind: "demo" | "log" | "missing" | "error";
  text: string;
}

export interface Watch {
  rows: FeedRow[]; // the chat, oldest first; matches carry their entry
  counters: [number, number, number]; // found, reacted, missed
  state: Record<number, AlertState>; // finished alerts by id
  remaining: Record<number, number>; // seconds left of the waiting alerts
  toasts: Toast[];
  source: Source;
  nag: boolean; // matches wait for «Принять» (alert_mode «nag»)
  watching: boolean;
  setWatching(on: boolean): void;
  system: boolean; // «Система»: system notices in «Весь чат»
  setSystem(on: boolean): void;
  since: string; // when the counters were last reset (ISO), "" when never
  checked: Set<string>;
  setChecked(ids: Set<string>): void;
  accept(alertId: number): void;
  acceptToast(toast: Toast): void;
  snoozeToast(toast: Toast): void;
  dismissToast(toast: Toast): void;
  /** The toast on screen with this notification id (the overlay names toasts by id). */
  toastById(id: number): Toast | undefined;
  reset(): void;
  /** The alert sound, to try it in the settings. */
  playSound(): void;
}

interface Tally { found: number; reacted: number; missed: number; since: string }
const COUNTERS_FILE = "counters.json"; // next to config.json: the counters live until «Сбросить»

const now = () => performance.now() / 1000;
/** The naive local wall clock in ms, the clock of Chat.log lines. */
const wallClock = () => {
  const d = new Date();
  return naiveMs(d.getFullYear(), d.getMonth() + 1, d.getDate(), d.getHours(), d.getMinutes(), d.getSeconds());
};
const SNOOZE_SEC = 300;
const MAX_TOASTS = 3;
const TOAST_SHOWN_SEC = 14;
const DEMO_STEP_MS = 3500;
const MAX_ROWS = 800; // the chat feed keeps the newest rows

/** The watching session of the screen: the real core (session, alerts, notifications) on Chat.log or demo lines. */
export function useWatch(boot: Boot): Watch {
  const demo = boot.platform === null;
  const cfg = boot.config;
  const nag = cfg.alert_mode === "nag";
  const core = useMemo(() => {
    const session = new WatchSession(itemNames, mapNames, questNames, {
      keywords: cfg.keywords, mode: cfg.search_mode,
      alertMode: nag ? "nag" : "standard", reactSec: cfg.react_sec, cooldownSec: cfg.cooldown_sec,
    });
    const center = new NotificationCenter({ clock: now });
    return { session, center, bridge: new AlertBridge(center) };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- one session per window, settings flow in below
  const { session, center, bridge } = core;
  const play = useMemo(() => makeSound(boot.platform, cfg), [boot.platform, cfg.sound_path, cfg.sound_volume]); // eslint-disable-line react-hooks/exhaustive-deps
  const quiet = cfg.notify_dnd || cfg.notify_off.includes("chat") || cfg.notify_mute.includes("chat");

  const [rows, setRows] = useState<FeedRow[]>([]);
  const [system, setSystemValue] = useState(cfg.chat_system);
  const rowKey = useRef(0);
  const [counters, setCounters] = useState<[number, number, number]>([0, 0, 0]);
  const [state, setState] = useState<Record<number, AlertState>>({});
  const [remaining, setRemaining] = useState<Record<number, number>>({});
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [source, setSourceValue] = useState<Source>(demo ? { kind: "demo", text: "Демо: строки чата придумываются" } : { kind: "log", text: boot.chatLog });
  const [watching, setWatching] = useState(true);
  const [checked, setCheckedIds] = useState<Set<string>>(() => new Set(cfg.watch_items.filter((id) => itemById[id])));
  const [tally, setTally] = useState<Tally>({ found: 0, reacted: 0, missed: 0, since: "" }); // earlier sessions
  const tallyLoaded = useRef(false);
  const step = useRef(0);
  const openToasts = useRef<Toast[]>([]); // the toast stack, kept outside React state: popping the queue is not repeatable
  const shownAt = useRef(new Map<number, number>()); // notification id -> when its toast appeared
  const icons = useRef(new Map<number, string | null>()); // notification id -> item picture

  const setSource = useCallback((next: Source) => // a new value only when it changes: polls come every 0.5 s
    setSourceValue((old) => (old.kind === next.kind && old.text === next.text ? old : next)), []);
  const showToasts = useCallback((list: Toast[]) => { openToasts.current = list; setToasts(list); }, []);
  const sync = useCallback(() => setCounters(session.counters), [session]);

  // settings changed in the panel reach the running session at once
  useEffect(() => { session.setKeywords(cfg.keywords); }, [session, cfg.keywords]);
  useEffect(() => { session.setMode(cfg.search_mode); }, [session, cfg.search_mode]);
  useEffect(() => { session.setAlertMode(cfg.alert_mode); }, [session, cfg.alert_mode]);
  useEffect(() => { session.tracker.react_sec = cfg.react_sec; }, [session, cfg.react_sec]);
  useEffect(() => { session.matcher.cooldown_sec = cfg.cooldown_sec; }, [session, cfg.cooldown_sec]);

  // the counters of earlier sessions, kept in counters.json until «Сбросить»
  useEffect(() => {
    const files = boot.platform;
    const path = boot.ownFile(COUNTERS_FILE);
    if (files === null || !path) { tallyLoaded.current = true; return; }
    files.readText(path).then((text) => {
      try {
        const data = text ? JSON.parse(text) : {};
        const n = (v: unknown) => (Number.isInteger(v) && (v as number) >= 0 ? (v as number) : 0);
        setTally({ found: n(data.found), reacted: n(data.reacted), missed: n(data.missed), since: typeof data.since === "string" ? data.since : "" });
      } catch { /* a broken file starts from zero */ }
      tallyLoaded.current = true;
    });
  }, [boot.platform, boot.ownFile]);
  const total: [number, number, number] = [tally.found + counters[0], tally.reacted + counters[1], tally.missed + counters[2]];
  useEffect(() => { // written a moment after a change
    const files = boot.platform;
    const path = boot.ownFile(COUNTERS_FILE);
    if (files === null || !path || !tallyLoaded.current) return;
    const timer = setTimeout(() => {
      files.writeText(path, JSON.stringify({ found: total[0], reacted: total[1], missed: total[2], since: tally.since }, null, 2)).catch(() => {});
    }, 500);
    return () => clearTimeout(timer);
  }, [total[0], total[1], total[2], tally.since]); // eslint-disable-line react-hooks/exhaustive-deps

  const finish = useCallback((ids: number[], how: AlertState) => {
    if (!ids.length) return;
    bridge.alertsDone(ids);
    setState((old) => ({ ...old, ...Object.fromEntries(ids.map((id) => [id, how])) }));
    sync();
  }, [bridge, sync]);

  const watchNames = useCallback((ids: Set<string>) => {
    const names: Record<string, string> = {};
    for (const item of watchItems) if (ids.has(item.id)) names[item.id] = item.name;
    session.setWatchItems(names);
  }, [session]);

  /** Lines in the feed with their matches; `history` lines are only shown, never announced. */
  const addRows = useCallback((lines: string[], entries: Parameters<typeof makeRows>[1], historic = false) => {
    const fresh = makeRows(lines, entries, () => ++rowKey.current, itemNames, mapNames, questNames, historic);
    if (fresh.length) setRows((list) => [...list, ...fresh].slice(-MAX_ROWS));
  }, []);

  /** New lines through the session: the feed, the counters and one notification per batch of matches. */
  const take = useCallback((lines: string[]) => {
    const batch = session.process(lines, now());
    addRows(lines, batch.entries);
    const loud = batch.entries.filter((e) => e.kind === LOUD);
    if (loud.length) {
      const note = bridge.chatMatch(loud.map((e) => e.alert_id!), loud.map((e) => [e.msg.nick, e.msg.text.replace(/[⟪⟫]/g, ""), e.hits]), nag);
      const item = loud.flatMap((e) => e.msg.item_ids.map((id) => itemById[id])).find(Boolean);
      if (note) icons.current.set(note.id, item?.icon ?? null);
      if (!quiet) play();
    }
    sync();
  }, [session, bridge, nag, sync, play, quiet, addRows]);

  useEffect(() => { watchNames(checked); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { // demo: the history of the last hour, then a made-up line every few seconds
    if (!demo) return;
    if (step.current === 0) {
      const lines: string[] = [];
      const base = new Date(Date.now() - 16 * 150_000);
      for (let i = 0; i < 16; i++, step.current++) lines.push(demoLine(step.current, new Date(base.getTime() + i * 150_000)));
      addRows(lines, session.history(lines, now()).entries, true);
      sync();
    }
    if (!watching) return;
    const timer = setInterval(() => take([demoLine(step.current++, new Date())]), DEMO_STEP_MS);
    return () => clearInterval(timer);
  }, [demo, watching, session, take, sync, addRows]);

  useEffect(() => { // the program: Chat.log, read every poll_interval_ms while watching
    const files = boot.platform;
    if (files === null || !watching) return;
    const path = boot.chatLog;
    const feed = new AsyncLogFeed({ size: () => files.fileSize(path), read: (p, n) => files.readRange(path, p, n) },
      Math.max(cfg.history_min, cfg.chat_minutes), wallClock); // one feed: the longer of the two histories
    let busy = false;
    let alive = true;
    const poll = async () => {
      if (busy) return;
      busy = true;
      try {
        const [history, lines] = await feed.poll();
        if (!alive) return;
        if (history !== null) addRows(history, session.history(history, now()).entries, true);
        if (lines.length) take(lines);
        setSource({ kind: "log", text: path });
      } catch (error) {
        if (!alive) return;
        const missing = (error as { code?: string }).code === "ENOENT";
        setSource(missing ? { kind: "missing", text: `Не найден Chat.log: ${path}. Проверь папку игры в настройках.` }
          : { kind: "error", text: `Не удалось прочитать Chat.log: ${error}` });
      } finally {
        busy = false;
      }
    };
    poll();
    const timer = setInterval(poll, Math.max(200, cfg.poll_interval_ms));
    return () => { alive = false; clearInterval(timer); session.stop(); };
  }, [boot.platform, boot.chatLog, watching, cfg.history_min, cfg.chat_minutes, cfg.poll_interval_ms, session, take, setSource, addRows]);

  useEffect(() => { // every second: countdowns, missed alerts, repeats, the toast stack
    const timer = setInterval(() => {
      const t = now();
      finish(session.expire(t), "missed");
      setRemaining(session.remaining(t));
      center.tick();
      const alive = openToasts.current.filter((toast) => center.isActive(toast.note) && t - (shownAt.current.get(toast.note.id) ?? t) < TOAST_SHOWN_SEC);
      const out = [...alive];
      for (let next = out.length < MAX_TOASTS ? center.popNext() : null; next; next = out.length < MAX_TOASTS ? center.popNext() : null) {
        if (out.some((toast) => toast.note.id === next!.id)) continue;
        shownAt.current.set(next.id, t);
        out.push({ note: next, icon: icons.current.get(next.repeat_key ?? next.id) ?? null });
      }
      if (out.length !== openToasts.current.length || out.some((toast, i) => toast !== openToasts.current[i])) showToasts(out);
    }, 1000);
    return () => clearInterval(timer);
  }, [session, center, finish, showToasts]);

  return {
    rows, counters: total, since: tally.since, state, system,
    setSystem: (on) => { setSystemValue(on); boot.save({ chat_system: on }); }, remaining, toasts, source, nag, watching, setWatching, checked,
    setChecked: (ids) => {
      setCheckedIds(ids);
      watchNames(ids);
      boot.save({ watch_items: watchItems.filter((item) => ids.has(item.id)).map((item) => item.id) });
    },
    accept: (alertId) => finish(session.accept(alertId), "accepted"),
    acceptToast: (toast) => {
      finish(bridge.toastAccepted(toast.note).flatMap((id) => session.accept(id)), "accepted");
      center.acknowledge(toast.note.id);
      showToasts(openToasts.current.filter((x) => x !== toast));
    },
    snoozeToast: (toast) => { center.snooze(toast.note.id, SNOOZE_SEC); showToasts(openToasts.current.filter((x) => x !== toast)); },
    dismissToast: (toast) => showToasts(openToasts.current.filter((x) => x !== toast)),
    toastById: (id) => openToasts.current.find((toast) => toast.note.id === id),
    reset: () => { session.resetCounters(); setTally({ found: 0, reacted: 0, missed: 0, since: new Date().toISOString() }); sync(); },
    playSound: () => play(),
  };
}
