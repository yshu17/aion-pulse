/**
 * Parse Aion Chat.log lines: any channel (ChatLine) and the «Поиск группы» search view (ChatMessage) — the port of
 * core/chat/parser.py. Reads no files: names come in as maps «id -> name».
 *
 *   names   item and recipe names     [item:166000103] -> [Меч Фланаса]
 *   maps    map (zone) names          [pos:Место;220070000 …] -> ⟪Место · Келькмарос¦220070000 x y⟫
 *   quests  quest names               [quest:2058] -> ⟪Задание: …⟫
 *
 * Python's «.» does not match «\n» only, so the patterns use [^\n] where Python has «.».
 */

import { pyFloat, pySplit } from "../py";

export const CHANNEL = "[3.Поиск группы]";
export const LFG_PREFIX = "3."; // channel 3 is «Поиск группы»; broken encodings keep the «3.»

const TIME_RE = /^(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) : ([^\n]*)$/;
const CHANNEL_RE = /^\[(?!charname:|item|cmd:|where:|pos:|quest:|recipe:)([^\]]+)\] ?([^\n]*)$/;
const CHARNAME_RE = /^\[charname:([^;\]]+);([^\]]*)\](?: ([^:[]{1,20}))?: ?([^\n]*)$/;
const PLAIN_NICK_RE = /^([^\s:[\]]{2,24}): ([^\n]*)$/;
const CMD_RE = /\[cmd:[^\]]*\]/g;
const ITEM_RE = /\[(?:item|item_ex|recipe):(\d*)[^\]]*\]/g;
const POS_RE = /\[pos:([^;\]]*);(?:\d )?(\d+) ([\d.-]+) ([\d.-]+)[^\]]*\]/g;
const QUEST_RE = /\[quest:(\d+)[^\]]*\]/g;
const WHERE_RE = /\[where:([^\]]*)\]/g;
const CUT_LINK_RE = /\[(?:where|pos|quest|item|item_ex|recipe|cmd):([^\]]*)$/;
const EMOTES_RE = /\?{3,}/g; // each chat smiley is written as «?»: runs of three and more are dropped
const SPACES_RE = / {2,}/g;

export const LINK_OPEN = "⟪";
export const LINK_CLOSE = "⟫";
export const POS_SEP = "¦"; // a place link keeps «map x y» after this mark

export interface ChatMessage {
  time: string;
  nick: string;
  text: string;
  raw: string;
  item_ids: string[];
}

export interface ChatLine {
  time: string;
  channel: string | null;
  nick: string | null;
  text: string;
  raw: string;
  item_ids: string[];
  color: string | null; // name colour «r g b» from [charname:…]
  verb: string; // «шепчет», «кричит» … between the name and the colon
}

export type Names = Record<string, string> | null | undefined;
export type Place3 = [string, number, number];

export function isPlayer(line: ChatLine): boolean {
  return line.nick !== null;
}

/** Python str.strip(). */
const strip = (text: string) => text.trim();

function placeLink(label: string, mapId: string, x: string, y: string, maps: Record<string, string>): string {
  const shownLabel = label || "Место";
  const region = maps[mapId];
  const shown = region ? `${shownLabel} · ${region}` : shownLabel;
  return `${LINK_OPEN}${shown}${POS_SEP}${mapId} ${x} ${y}${LINK_CLOSE}`;
}

function questLink(id: string, quests: Record<string, string>): string {
  const name = quests[id];
  return name ? `${LINK_OPEN}Задание: ${name}${LINK_CLOSE}` : `${LINK_OPEN}Задание ${id}${LINK_CLOSE}`;
}

/** «Место · Келькмарос¦220070000 2010.1 1315.8» -> ["Место · Келькмарос", ["220070000", 2010.1, 1315.8]]. */
export function splitPlace(link: string): [string, Place3 | null] {
  const at = link.indexOf(POS_SEP);
  if (at < 0) return [link, null];
  const shown = link.slice(0, at);
  const parts = pySplit(link.slice(at + POS_SEP.length));
  if (parts.length !== 3) return [shown, null];
  const x = pyFloat(parts[1]);
  const y = pyFloat(parts[2]);
  if (x === null || y === null) return [shown, null];
  return [shown, [parts[0], x, y]];
}

const LINK_BODY = new RegExp(`${LINK_OPEN}([^${LINK_OPEN}${LINK_CLOSE}]*)${LINK_CLOSE}`, "g");

/** Place links of a cleaned message: [[label, [map id, x, y]], ...]. */
export function placesIn(text: string): [string, Place3][] {
  const found: [string, Place3][] = [];
  for (const match of text.matchAll(LINK_BODY)) {
    const [shown, place] = splitPlace(match[1]);
    if (place !== null) found.push([shown, place]);
  }
  return found;
}

/** Message text as the user sees it: links as <…>, place coordinates hidden. */
export function displayText(text: string): string {
  return text.replace(LINK_BODY, (_m, body: string) => `<${splitPlace(body)[0]}>`);
}

function cutLink(whole: string, body: string): string {
  if (whole.startsWith("[where:") && strip(body)) return `${LINK_OPEN}${strip(body)}…${LINK_CLOSE}`;
  return "…";
}

const unknownItem = (id: string) => (id ? `Предмет ${id}` : "Предмет");

/**
 * Drop [cmd:...] markup and make links readable: item / recipe links become [name] ([Предмет 166000103] when unknown);
 * place, quest and «where» links become ⟪Место · Келькмарос⟫, ⟪Задание 2058⟫, ⟪text⟫; runs of «???» are dropped.
 */
export function cleanText(text: string, names?: Names, maps?: Names, quests?: Names): string {
  const n = names ?? {};
  const m = maps ?? {};
  const q = quests ?? {};
  let out = text.trimEnd().replace(CUT_LINK_RE, (whole, body) => cutLink(whole, body));
  out = out.replace(CMD_RE, "");
  out = out.replace(ITEM_RE, (_w, id: string) => `[${n[id] || unknownItem(id)}]`);
  out = out.replace(POS_RE, (_w, label, mapId, x, y) => placeLink(label, mapId, x, y, m));
  out = out.replace(QUEST_RE, (_w, id) => questLink(id, q));
  out = out.replace(WHERE_RE, (_w, body: string) => `${LINK_OPEN}${strip(body)}${LINK_CLOSE}`);
  out = out.replace(EMOTES_RE, "").replace(SPACES_RE, " ");
  return strip(out);
}

/** Split a timestamped log line into channel, nick and text; null for lines without a time. */
export function parseAnyLine(line: string, names?: Names, maps?: Names, quests?: Names): ChatLine | null {
  const raw = line.replace(/[\r\n]+$/, "");
  const match = TIME_RE.exec(raw);
  if (match === null) return null;
  const time = match[1];
  let rest = match[2];
  let channel: string | null = null;
  const channelMatch = CHANNEL_RE.exec(rest);
  if (channelMatch !== null) {
    channel = channelMatch[1];
    rest = channelMatch[2];
  }
  let nick: string | null = null;
  let color: string | null = null;
  let verb = "";
  const nickMatch = CHARNAME_RE.exec(rest);
  if (nickMatch !== null) {
    nick = nickMatch[1];
    color = nickMatch[2];
    verb = strip(nickMatch[3] ?? "");
    rest = nickMatch[4];
  } else if (channel !== null && channel.startsWith(LFG_PREFIX)) {
    const plain = PLAIN_NICK_RE.exec(rest);
    if (plain !== null) {
      nick = plain[1];
      rest = plain[2];
    }
  }
  const itemIds = [...rest.matchAll(ITEM_RE)].map((m) => m[1]).filter((id) => id !== "");
  return { time, channel, nick, text: cleanText(rest, names, maps, quests), raw, item_ids: itemIds, color, verb };
}

/** The message for a player line in «Поиск группы», else null. */
export function parseLine(line: string, names?: Names, maps?: Names, quests?: Names): ChatMessage | null {
  const parsed = parseAnyLine(line, names, maps, quests);
  if (parsed === null || parsed.nick === null || !(parsed.channel ?? "").startsWith(LFG_PREFIX)) return null;
  return { time: parsed.time, nick: parsed.nick, text: parsed.text, raw: parsed.raw, item_ids: parsed.item_ids };
}
