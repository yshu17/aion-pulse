/**
 * Chat alerts and «the game is not running» as notifications — the port of core/notify/alert_bridge.py.
 *
 *   chatMatch(alertIds, entries, nag)  one notification per batch of matches; entries are [nick, text, hits]
 *   toastAccepted(event)               «Принять» on it: the alert ids to accept (once)
 *   alertsDone(ids)                    alerts accepted in the feed or missed: a notification whose alerts are all done closes
 *   gameRunning(running)               «Проверить снова» when the game stops; closed when it is back
 */

import { Notification, NotificationCenter } from "./center";

export const CHAT = "chat";
export const STATUS = "status";
export const GAME_OFF_TITLE = "Игра не запущена";
export const GAME_OFF_TEXT = "После запуска Aion нажми «Проверить снова».";

export class AlertBridge {
  private alerts = new Map<number, Set<number>>(); // notification id -> alert ids still waiting
  private gameOff: Notification | null = null;

  constructor(private center: NotificationCenter) {}

  chatMatch(alertIds: number[], entries: [string, string, string[]][], nag: boolean): Notification | null {
    if (!entries.length) return null;
    const [nick, text] = entries[0];
    const words = [...new Set(entries.flatMap(([, , hits]) => hits))].join(", ");
    const more = entries.length > 1 ? ` (и ещё ${entries.length - 1})` : "";
    const actions = nag ? [{ id: "accept", label: "Принять" }] : [];
    const note = this.center.notify(CHAT, "chat", `Найдено в чате: ${words}`, `${nick}: ${text}${more}`, actions, !nag);
    if (note !== null && nag && alertIds.length) this.alerts.set(note.id, new Set(alertIds));
    return note;
  }

  toastAccepted(event: Notification | null): number[] {
    if (event === null) return [];
    const key = event.repeat_key ?? event.id;
    const ids = this.alerts.get(key) ?? new Set<number>();
    this.alerts.delete(key);
    return [...ids].sort((a, b) => a - b);
  }

  alertsDone(alertIds: number[]): void {
    const done = new Set(alertIds);
    for (const [noteId, waiting] of [...this.alerts]) {
      for (const id of done) waiting.delete(id);
      if (!waiting.size) {
        this.alerts.delete(noteId);
        this.center.acknowledge(noteId);
      }
    }
  }

  gameRunning(running: boolean): Notification | null {
    if (running) {
      if (this.gameOff !== null) {
        this.center.acknowledge(this.gameOff.id);
        this.gameOff = null;
      }
      return null;
    }
    if (this.gameOff !== null) return null;
    this.gameOff = this.center.notify(STATUS, "warning", GAME_OFF_TITLE, GAME_OFF_TEXT,
      [{ id: "retry", label: "Проверить снова" }]);
    return this.gameOff;
  }
}
