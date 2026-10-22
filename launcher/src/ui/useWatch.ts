import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Entry, LOUD, WatchSession } from "../core/chat/session";
import { AlertBridge } from "../core/notify/bridge";
import { Notification, NotificationCenter } from "../core/notify/center";
import { demoLine, itemById, itemNames, mapNames, questNames, watchItems } from "./data";

export type AlertState = "accepted" | "missed";

export interface Toast {
  note: Notification;
  icon: string | null;
}

export interface Watch {
  entries: Entry[];
  counters: [number, number, number]; // found, reacted, missed
  state: Record<number, AlertState>; // finished alerts by id
  remaining: Record<number, number>; // seconds left of the waiting alerts
  toasts: Toast[];
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
  reset(): void;
}

const now = () => performance.now() / 1000;
const REACT_SEC = 30;
const SNOOZE_SEC = 300;
const MAX_TOASTS = 3;
const TOAST_SHOWN_SEC = 14;
const START = ["110600968", "114600926", "113600931"].filter((id) => itemById[id]);

/** The watching session of the screen: the real core (session, alerts, notifications) on demo chat lines. */
export function useWatch(): Watch {
  const core = useMemo(() => {
    const session = new WatchSession(itemNames, mapNames, questNames, {
      keywords: ["wts", "продам", "ищу группу"], mode: "or", alertMode: "nag", reactSec: REACT_SEC,
    });
    const center = new NotificationCenter({ clock: now });
    return { session, center, bridge: new AlertBridge(center) };
  }, []);
  const { session, center, bridge } = core;

  const [entries, setEntries] = useState<Entry[]>([]);
  const [counters, setCounters] = useState<[number, number, number]>([0, 0, 0]);
  const [state, setState] = useState<Record<number, AlertState>>({});
  const [remaining, setRemaining] = useState<Record<number, number>>({});
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [watching, setWatching] = useState(true);
  const [keywords, setKeywordsText] = useState("wts, продам, ищу группу");
  const [mode, setModeValue] = useState("or");
  const [checked, setCheckedIds] = useState<Set<string>>(new Set(START));
  const step = useRef(0);
  const openToasts = useRef<Toast[]>([]); // the toast stack, kept outside React state: popping the queue is not repeatable
  const shownAt = useRef(new Map<number, number>()); // notification id -> when its toast appeared
  const icons = useRef(new Map<number, string | null>()); // notification id -> item picture

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

  useEffect(() => { // the first poll: the history of the last hour, no alerts
    watchNames(checked);
    const lines: string[] = [];
    const base = new Date(Date.now() - 16 * 150_000);
    for (let i = 0; i < 16; i++, step.current++) lines.push(demoLine(step.current, new Date(base.getTime() + i * 150_000)));
    setEntries(session.history(lines, now()).entries);
    sync();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { // a new chat line every few seconds
    if (!watching) return;
    const timer = setInterval(() => {
      const batch = session.process([demoLine(step.current++, new Date())], now());
      if (batch.entries.length) setEntries((list) => [...list, ...batch.entries].slice(-300));
      const loud = batch.entries.filter((e) => e.kind === LOUD);
      if (loud.length) {
        const note = bridge.chatMatch(loud.map((e) => e.alert_id!), loud.map((e) => [e.msg.nick, e.msg.text.replace(/[⟪⟫]/g, ""), e.hits]), true);
        if (note) icons.current.set(note.id, loud.map((e) => e.msg.item_ids.map((id) => itemById[id]).find(Boolean)).find(Boolean)?.icon ?? null);
      }
      sync();
    }, 3500);
    return () => clearInterval(timer);
  }, [session, bridge, watching, sync]);

  useEffect(() => { // every second: countdowns, missed alerts, repeats, the toast stack
    const timer = setInterval(() => {
      const t = now();
      finish(session.expire(t), "missed");
      setRemaining(session.remaining(t));
      center.tick();
      const alive = openToasts.current.filter((toast) => center.isActive(toast.note) && t - (shownAt.current.get(toast.note.id) ?? t) < TOAST_SHOWN_SEC);
      const out = [...alive];
      for (let next = out.length < MAX_TOASTS ? center.popNext() : null; next; next = out.length < MAX_TOASTS ? center.popNext() : null) {
        shownAt.current.set(next.id, t);
        out.push({ note: next, icon: icons.current.get(next.repeat_key ?? next.id) ?? null });
      }
      if (out.length !== openToasts.current.length || out.some((toast, i) => toast !== openToasts.current[i])) showToasts(out);
    }, 1000);
    return () => clearInterval(timer);
  }, [session, center, finish, showToasts]);

  return {
    entries, counters, state, remaining, toasts, watching, setWatching, keywords, mode, checked,
    setKeywords: (text) => {
      setKeywordsText(text);
      session.setKeywords(text.split(",").map((part) => part.trim()).filter(Boolean));
    },
    setMode: (value) => { setModeValue(value); session.setMode(value); },
    setChecked: (ids) => { setCheckedIds(ids); watchNames(ids); },
    accept: (alertId) => finish(session.accept(alertId), "accepted"),
    acceptToast: (toast) => {
      finish(bridge.toastAccepted(toast.note).flatMap((id) => session.accept(id)), "accepted");
      center.acknowledge(toast.note.id);
      showToasts(openToasts.current.filter((x) => x !== toast));
    },
    snoozeToast: (toast) => { center.snooze(toast.note.id, SNOOZE_SEC); showToasts(openToasts.current.filter((x) => x !== toast)); },
    dismissToast: (toast) => showToasts(openToasts.current.filter((x) => x !== toast)),
    reset: () => { session.resetCounters(); sync(); },
  };
}
