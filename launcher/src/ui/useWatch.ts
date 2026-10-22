import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Entry, WatchSession } from "../core/chat/session";
import { demoLine, itemNames, mapNames, questNames, watchItems } from "./data";

export interface Watch {
  entries: Entry[];
  counters: [number, number, number]; // found, reacted, missed
  watching: boolean;
  setWatching(on: boolean): void;
  keywords: string;
  setKeywords(text: string): void;
  mode: string;
  setMode(mode: string): void;
  checked: Set<string>;
  setChecked(ids: Set<string>): void;
  reset(): void;
}

const now = () => performance.now() / 1000;
const DEFAULT_CHECKED = ["110600968", "114600926", "113600931"];
const START = watchItems.filter((item) => DEFAULT_CHECKED.includes(item.id)).map((item) => item.id);

/** The watching session of the screen: the real core on demo chat lines, one new line every few seconds. */
export function useWatch(): Watch {
  const session = useMemo(() => new WatchSession(itemNames, mapNames, questNames, {
    keywords: ["wts", "продам", "ищу группу"], mode: "or", alertMode: "standard",
  }), []);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [counters, setCounters] = useState<[number, number, number]>([0, 0, 0]);
  const [watching, setWatching] = useState(true);
  const [keywords, setKeywordsText] = useState("wts, продам, ищу группу");
  const [mode, setModeValue] = useState("or");
  const [checked, setCheckedIds] = useState<Set<string>>(new Set(START));
  const step = useRef(0);

  const apply = useCallback((ids: Set<string>) => {
    const names: Record<string, string> = {};
    for (const item of watchItems) if (ids.has(item.id)) names[item.id] = item.name;
    session.setWatchItems(names);
  }, [session]);

  useEffect(() => {
    apply(checked);
    const lines: string[] = [];
    const base = new Date(Date.now() - 16 * 150_000);
    for (let i = 0; i < 16; i++, step.current++) lines.push(demoLine(step.current, new Date(base.getTime() + i * 150_000)));
    const batch = session.history(lines, now());
    setEntries(batch.entries);
    setCounters(session.counters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!watching) return;
    const timer = setInterval(() => {
      const batch = session.process([demoLine(step.current++, new Date())], now());
      if (batch.entries.length) setEntries((list) => [...list, ...batch.entries].slice(-300));
      setCounters(session.counters);
    }, 3500);
    return () => clearInterval(timer);
  }, [session, watching]);

  return {
    entries, counters, watching, setWatching, keywords, mode, checked,
    setKeywords: (text) => {
      setKeywordsText(text);
      session.setKeywords(text.split(",").map((part) => part.trim()).filter(Boolean));
    },
    setMode: (value) => { setModeValue(value); session.setMode(value); },
    setChecked: (ids) => { setCheckedIds(ids); apply(ids); },
    reset: () => { session.resetCounters(); setCounters(session.counters); },
  };
}
