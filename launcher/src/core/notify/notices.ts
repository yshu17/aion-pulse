/**
 * Which notification to raise for a program event, and what a button on a notification means — the port of
 * core/notify/notices.py.
 */

import { decide } from "../schedule/scheduleUpdate";
import { newer } from "../update/updater";

export interface Notice {
  source: string;
  kind: string;
  title: string;
  text: string;
  actions: [string, string][];
}

/** A newer release the user has not dismissed yet. `found` = [tag, page url] of the latest release. */
export function releaseNotice(found: [string, string] | null, canInstall: boolean, current: string, seen: string): Notice | null {
  if (found === null || !newer(found[0], current) || found[0] === seen) return null;
  if (canInstall) {
    return {
      source: "app", kind: "event", title: `Доступна новая версия ${found[0]}`,
      text: "Pulse скачает Pulse.exe с GitHub, проверит контрольную сумму и перезапустится. Ничего без твоего «да».",
      actions: [["install", "Обновить сейчас"], ["release", "Открыть релиз"], ["accept", "Позже"]],
    };
  }
  return {
    source: "app", kind: "event", title: `Доступна новая версия ${found[0]}`,
    text: "Открой страницу релиза и скачай новый Pulse.exe. Программа сама ничего не скачивает.",
    actions: [["release", "Открыть релиз"], ["accept", "Понятно"]],
  };
}

/** status «ok» with the site fingerprint in `value`, or «err» with the error text. */
export function scheduleCheckNotice(status: string, value: string, known: string, seen: string, manual: boolean): Notice | null {
  if (status === "err") {
    return manual ? { source: "schedule", kind: "warning", title: "Не удалось проверить расписание",
      text: [...value].slice(0, 120).join(""), actions: [] } : null;
  }
  const verdict = decide(known, value, seen, manual);
  if (verdict === "same") {
    return { source: "schedule", kind: "event", title: "Расписание актуально",
      text: "Картинка в базе знаний та же, по которой составлена сетка программы.", actions: [] };
  }
  if (verdict === "changed") {
    return { source: "schedule", kind: "event", title: "Расписание на сайте обновилось",
      text: "Картинка в базе знаний новая — сверь сетку; data/schedule.json правится вручную.",
      actions: [["site", "Открыть статью"], ["accept", "Понятно"]] };
  }
  return null;
}

/**
 * What a button press means. `key` is the notification id (or its repeat key); the other two are the ids of the
 * release and schedule-check notifications currently shown.
 */
export function routeAction(action: string, key: number | null, releaseKey: number | null, scheduleKey: number | null): string {
  const isRelease = releaseKey !== null && key === releaseKey;
  if (action === "site") return "open_site";
  if (action === "install" && isRelease) return "install";
  if (action === "release" && isRelease) return "open_release";
  if (action === "accept" && isRelease) return "release_seen";
  if (action === "accept" && scheduleKey !== null && key === scheduleKey) return "schedule_seen";
  if (action === "accept") return "accept_alerts";
  if (action === "retry") return "retry";
  return "open";
}
