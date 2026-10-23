// One chat feed for «Совпадения» and «Весь чат»: every Chat.log line becomes a row; the lines the session matched
// carry their match (card, timer, «Принять»). The rules of what «Весь чат» shows are Pulse's (watcher/allchat.py).
import { category, isNotice } from "../core/chat/categories";
import { ChatLine, parseAnyLine } from "../core/chat/parser";
import type { Entry } from "../core/chat/session";

export type FeedMode = "matches" | "all";

export interface FeedRow {
  key: number; // stable for React: rows come and go at both ends
  line: ChatLine;
  category: string | null; // «Поиск группы», «Общий», «Личное», «Группа», «Легион»; null for system lines
  notice: boolean; // a system line of «Информация и уведомления»
  entry: Entry | null; // the match of this line
  historic: boolean; // from the history read at the start, not a live line
}

export const CHANNEL_COLORS: Record<string, string> = { // watcher/theme.py CHAT_COLORS
  "Поиск группы": "#ffb45e", "Общий": "#e9e7e4", "Личное": "#a0ffa0", "Группа": "#05c8d7", "Легион": "#9ce7dc",
};

type Names = Record<string, string>;

/** Rows for log lines in order; `entries` are the session's matches of the same lines (by raw text, in order). */
export function makeRows(lines: string[], entries: Entry[], nextKey: () => number, names: Names, maps: Names, quests: Names,
                         historic = false): FeedRow[] {
  const byRaw = new Map<string, Entry[]>();
  for (const entry of entries) {
    const raw = entry.msg.raw;
    byRaw.set(raw, [...(byRaw.get(raw) ?? []), entry]);
  }
  const rows: FeedRow[] = [];
  for (const text of lines) {
    const line = parseAnyLine(text, names, maps, quests);
    if (line === null) continue;
    const entry = byRaw.get(line.raw)?.shift() ?? null;
    const player = line.nick !== null;
    rows.push({ key: nextKey(), line, category: player ? category(line) : null, notice: !player && isNotice(line), entry, historic });
  }
  return rows;
}

/** What the feed shows: matches only, or the whole chat (system notices when asked). */
export function shown(row: FeedRow, mode: FeedMode, system: boolean): boolean {
  if (row.entry !== null) return true;
  if (mode === "matches") return false;
  return row.category !== null || (system && row.notice);
}

/** The channel label of a row, as Pulse writes it: «3.Поиск группы» for the group channel, else the category. */
export function channelLabel(row: FeedRow): string | null {
  if (row.category === "Поиск группы" && row.line.channel && !row.line.channel.includes("?")) return row.line.channel;
  return row.category ?? row.line.channel;
}
