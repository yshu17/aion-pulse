/**
 * Notification settings from config.json, applied to the center and the toast window — the port of
 * core/notify/notify_settings.py. Odd values fall back to the defaults.
 */

import type { NotificationCenter } from "./center";

export const SOURCES: [string, string][] = [["chat", "Совпадения в чате"], ["status", "Игра не запущена"],
  ["schedule", "Напоминания расписания"]];
export const CORNERS: Record<string, string> = { bottom: "Справа снизу", top: "Справа сверху" };
export const DURATIONS = [5, 8, 15];
export const STACK = [1, 2, 3];
export const DEFAULT_CORNER = "bottom";
export const DEFAULT_DURATION = 8;
export const DEFAULT_STACK = 3;

export interface NotifyConfig {
  notify_off: string[];
  notify_mute: string[];
  notify_dnd: boolean;
  notify_corner: string;
  notify_duration: number;
  notify_stack: number;
}

export interface ToastWindow {
  corner: string | null;
  duration: number | null;
  max_visible: number | null;
}

export function applyNotifySettings(cfg: NotifyConfig, center: NotificationCenter, manager: ToastWindow | null = null): void {
  for (const [source] of SOURCES) {
    center.setSource(source, !cfg.notify_off.includes(source), !cfg.notify_mute.includes(source));
  }
  center.do_not_disturb = Boolean(cfg.notify_dnd);
  if (manager !== null) {
    manager.corner = cfg.notify_corner in CORNERS ? cfg.notify_corner : DEFAULT_CORNER;
    manager.duration = DURATIONS.includes(cfg.notify_duration) ? cfg.notify_duration : DEFAULT_DURATION;
    manager.max_visible = STACK.includes(cfg.notify_stack) ? cfg.notify_stack : DEFAULT_STACK;
  }
}
