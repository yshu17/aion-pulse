// First start of Pulse+: take the settings of an old Pulse (its config.json) instead of the defaults.
import { Config, DEFAULTS, readConfig } from "../core/settings/config";

/** Keys that only a Pulse config.json has together; a stray config.json of another program is left alone. */
const PULSE_KEYS = ["game_dir", "keywords", "watch_items", "alert_mode"];

export interface Migration {
  config: Config;
  from: string;
  notice: string;
}

/** The first candidate that is a Pulse config.json, read as Pulse reads it; null when there is none. */
export function pulseSettings(candidates: [string, string | null][]): Migration | null {
  for (const [path, text] of candidates) {
    if (text === null) continue;
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      continue;
    }
    if (data === null || typeof data !== "object" || Array.isArray(data)) continue;
    const keys = Object.keys(data);
    if (PULSE_KEYS.filter((key) => keys.includes(key) && key in DEFAULTS).length < 2) continue;
    const result = readConfig(text);
    const wrong = result.notice ? ` (${result.notice})` : "";
    return { config: result.config, from: path, notice: `Настройки перенесены из Pulse: ${path}${wrong}` };
  }
  return null;
}
