/**
 * Which «Весь чат» category a log line belongs to, and which system lines are notices — the port of
 * core/chat/categories.py. Channel-less player lines are told apart by the name colour from [charname:Name;r g b].
 */

import { ChatLine, isPlayer } from "./parser";

const NAME_COLORS: Record<string, string> = {
  "1.0000 1.0000 1.0000": "Общий",
  "0.6275 1.0000 0.6275": "Личное",
  "0.0196 0.7843 0.8431": "Группа",
  "0.6118 0.9059 0.8627": "Легион",
};
const WHISPER_VERBS = new Set(["шепчет", "шепчете"]);
const NOTICE = new RegExp(
  "^(Получено|Получен[аы]?|Вы получили|Использовано|Невозможно|Нельзя|Недостаточно|Вы не можете|"
  + "Цель находится|Кто-то уже|Не удалось|Задание|Вы вошли|Вы покинули)"
  + "|получает: \\[|присоединил|покинул[аи]? (группу|легион)|кинар",
);

/** «Поиск группы», «Общий», «Личное», «Группа», «Легион» or null (not shown). */
export function category(line: ChatLine): string | null {
  const channel = line.channel ?? "";
  if (channel.startsWith("3.")) return "Поиск группы";
  if (channel.startsWith("1.")) return "Общий";
  if (channel) return null; // trade and other numbered channels
  if (WHISPER_VERBS.has(line.verb)) return "Личное";
  return NAME_COLORS[line.color ?? ""] ?? null;
}

/** System «information» and «errors / notifications» (loot, kinah, can't-do-that…), not combat. */
export function isNotice(line: ChatLine): boolean {
  if (isPlayer(line)) return false;
  if (line.channel !== null) return !line.channel.startsWith("?"); // [Event] …; unreadable ones are skipped
  return !line.text.includes("??") && NOTICE.test(line.text);
}
