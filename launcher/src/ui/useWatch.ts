import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Entry, LOUD, WatchSession } from "../core/chat/session";
import { naiveMs } from "../core/chat/tailer";
import { AlertBridge } from "../core/notify/bridge";
import { Notification, NotificationCenter } from "../core/notify/center";
import { demoLine, itemById, itemNames, mapNames, questNames, watchItems } from "./data";
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
  entries: Entry[];
  counters: [number, number, number]; // found, reacted, missed
  state: Record<number, AlertState>; // finished alerts by id
  remaining: Record<number, number>; // seconds left of the waiting alerts
  toasts: Toast[];
  source: Source;
  nag: boolean; // matches wait for «Принять» (alert_mode «nag»)
  watching: boolean;
  setWatching(on: boolean): void;
  keywords: string;
  setKeywords(text: string): void;
  mode: string;
  setMode(mode: string): void;
  checked: Set<string>;
  setChecked(ids: Set<string>): void;
  accept(alertId: number): void;
  acceptToast(toast: Toast): void;
  snoozeToast(toast: Toast): void;
  dismissToast(toast: Toast): void;
  /** The toast on screen with this notification id (the overlay names toasts by id). */
  toastById(id: number): Toast | undefined;
  reset(): void;
}

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
const DEMO_CHECKED = ["110600968", "114600926", "113600931"];
const splitWords = (text: string) => text.split(",").map((part) => part.trim()).filter(Boolean);

/** The watching session of the screen: the real core (session, alerts, notifications) on Chat.log or demo lines. */
export function useWatch(boot: Boot): Watch {
  const demo = boot.platform === null;
  const cfg = boot.config;
  const nag = demo || cfg.alert_mode === "nag";
  const core = useMemo(() => {
    const session = new WatchSession(itemNames, mapNames, questNames, {
      keywords: demo ? ["wts", "продам", "ищу группу"] : cfg.keywords, mode: cfg.search_mode,
      alertMode: nag ? "nag" : "standard", reactSec: cfg.react_sec, cooldownSec: cfg.cooldown_sec,
    });
    const center = new NotificationCenter({ clock: now });
    return { session, center, bridge: new AlertBridge(center) };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- one session per window, settings flow in below
  const { session, center, bridge } = core;
  const play = useMemo(() => makeSound(boot.platform, cfg), [boot.platform, cfg.sound_path, cfg.sound_volume]); // eslint-disable-line react-hooks/exhaustive-deps
  const quiet = cfg.notify_dnd || cfg.notify_off.includes("chat") || cfg.notify_mute.includes("chat");

  const [entries, setEntries] = useState<Entry[]>([]);
  const [counters, setCounters] = useState<[number, number, number]>([0, 0, 0]);
  const [state, setState] = useState<Record<number, AlertState>>({});
  const [remaining, setRemaining] = useState<Record<number, number>>({});
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [source, setSourceValue] = useState<Source>(demo ? { kind: "demo", text: "Демо: строки чата придумываются" } : { kind: "log", text: boot.chatLog });
  const [watching, setWatching] = useState(true);
  const [keywords, setKeywordsText] = useState(() => (demo ? "wts, продам, ищу группу" : cfg.keywords.join(", ")));
  const [mode, setModeValue] = useState(cfg.search_mode);
  const [checked, setCheckedIds] = useState<Set<string>>(() => new Set((demo ? DEMO_CHECKED : cfg.watch_items).filter((id) => itemById[id])));
  const step = useRef(0);
  const openToasts = useRef<Toast[]>([]); // the toast stack, kept outside React state: popping the queue is not repeatable
  const shownAt = useRef(new Map<number, number>()); // notification id -> when its toast appeared
  const icons = useRef(new Map<number, string | null>()); // notification id -> item picture

  const setSource = useCallback((next: Source) => // a new value only when it changes: polls come every 0.5 s
    setSourceValue((old) => (old.kind === next.kind && old.text === next.text ? old : next)), []);
  const showToasts = useCallback((list: Toast[]) => { openToasts.current = list; setToasts(list); }, []);
  const sync = useCallback(() => setCounters(session.counters), [session]);

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

  /** New lines through the session: the feed, the counters and one notification per batch of matches. */
  const take = useCallback((lines: string[]) => {
    const batch = session.process(lines, now());
    if (batch.entries.length) setEntries((list) => [...list, ...batch.entries].slice(-300));
    const loud = batch.entries.filter((e) => e.kind === LOUD);
    if (loud.length) {
      const note = bridge.chatMatch(loud.map((e) => e.alert_id!), loud.map((e) => [e.msg.nick, e.msg.text.replace(/[⟪⟫]/g, ""), e.hits]), nag);
      const item = loud.flatMap((e) => e.msg.item_ids.map((id) => itemById[id])).find(Boolean);
      if (note) icons.current.set(note.id, item?.icon ?? null);
      if (!quiet) play();
    }
    sync();
  }, [session, bridge, nag, sync, play, quiet]);

  useEffect(() => { watchNames(checked); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { // demo: the history of the last hour, then a made-up line every few seconds
    if (!demo) return;
    if (step.current === 0) {
      const lines: string[] = [];
      const base = new Date(Date.now() - 16 * 150_000);
      for (let i = 0; i < 16; i++, step.current++) lines.push(demoLine(step.current, new Date(base.getTime() + i * 150_000)));
      setEntries(session.history(lines, now()).entries);
      sync();
    }
    if (!watching) return;
    const timer = setInterval(() => take([demoLine(step.current++, new Date())]), DEMO_STEP_MS);
    return () => clearInterval(timer);
  }, [demo, watching, session, take, sync]);

  useEffect(() => { // the program: Chat.log, read every poll_interval_ms while watching
    const files = boot.platform;
    if (files === null || !watching) return;
    const path = boot.chatLog;
    const feed = new AsyncLogFeed({ size: () => files.fileSize(path), read: (p, n) => files.readRange(path, p, n) },
      cfg.history_min, wallClock);
    let busy = false;
    let alive = true;
    const poll = async () => {
      if (busy) return;
      busy = true;
      try {
        const [history, lines] = await feed.poll();
        if (!alive) return;
        if (history !== null) setEntries((list) => [...list, ...session.history(history, now()).entries].slice(-300));
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
  }, [boot.platform, boot.chatLog, watching, cfg.history_min, cfg.poll_interval_ms, session, take, setSource]);

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
    entries, counters, state, remaining, toasts, source, nag, watching, setWatching, keywords, mode, checked,
    setKeywords: (text) => {
      setKeywordsText(text);
      session.setKeywords(splitWords(text));
      if (!demo) boot.save({ keywords: splitWords(text) });
    },
    setMode: (value) => {
      setModeValue(value);
      session.setMode(value);
      if (!demo) boot.save({ search_mode: value });
    },
    setChecked: (ids) => {
      setCheckedIds(ids);
      watchNames(ids);
      if (!demo) boot.save({ watch_items: watchItems.filter((item) => ids.has(item.id)).map((item) => item.id) });
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
    reset: () => { session.resetCounters(); sync(); },
  };
}
