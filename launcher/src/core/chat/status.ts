/**
 * What the watching says about itself: the status line, its short chip and the empty feed — the port of
 * core/chat/status.py.
 */

import { plural } from "../text";

export const STOPPED = "Остановлен";
export const GAME_OFF = "Игра не запущена — слежение остановлено";
export const STATUS_CHARS = 20;
export const HINT_SEP = "  ·  ";

export const watchingStatus = (path: string, hint = "") => `Слежу за ${path}` + (hint ? `${HINT_SEP}${hint}` : "");
export const notFoundStatus = (path: string) => `Chat.log не найден: ${path}`;
export const errorStatus = (error: unknown) => `Ошибка: ${error}`;
export const readErrorStatus = (error: unknown) => `Ошибка чтения: ${error}`;
/** «— 18:05 Игра не запущена …: запусти игру и нажми Start —». */
export const gameOffNote = (clockHm: string) => `— ${clockHm} ${GAME_OFF}: запусти игру и нажми Start —`;

/** What the chosen search mode is missing, e.g. «нет ключевых слов»; "" when it can find something. */
export function searchHint(mode: string, keywords: string[], watchItems: string[]): string {
  const noWords = !keywords.length && ["words", "and", "or"].includes(mode);
  const noItems = !watchItems.length && ["items", "and", "or"].includes(mode);
  if (mode === "or" && !(noWords && noItems)) return "";
  const missing: string[] = [];
  if (noWords) missing.push("нет ключевых слов");
  if (noItems) missing.push("не отмечены предметы");
  return missing.join(", ");
}

/** [title, hint] of the empty feed. */
export function emptyFeed(running: boolean, mode: string, keywords: string[], watchItems: string[]): [string, string] {
  const missing = searchHint(mode, keywords, watchItems);
  const hint = missing ? `Сейчас ${missing}`
    : `Ищу: ${plural(keywords.length, "слово", "слова", "слов")}, ${plural(watchItems.length, "предмет", "предмета", "предметов")}`;
  return [running ? "Слежу — совпадений пока нет" : "Нажми Start — здесь появятся совпадения", hint];
}

/** The compact status of the chip and its kind: live, warn, error or idle. */
export function statusChip(text: string): [string, "live" | "warn" | "error" | "idle"] {
  if (text.startsWith("Слежу")) {
    const at = text.indexOf(HINT_SEP);
    const hint = at >= 0 ? text.slice(at + HINT_SEP.length) : "";
    return ["Слежу" + (hint ? `${HINT_SEP}${hint}` : ""), "live"];
  }
  if (text.startsWith("Игра не запущена")) return ["Игра не запущена", "warn"];
  if (text.startsWith("Chat.log не найден")) return ["Chat.log не найден", "warn"];
  if (text.startsWith("Ошибка")) {
    return [[...text].length <= STATUS_CHARS ? text : [...text].slice(0, STATUS_CHARS - 1).join("") + "…", "error"];
  }
  return ["Не слежу", "idle"];
}
