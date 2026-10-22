/**
 * The settings model of Pulse and reading / writing config.json — the port of core/settings/config.py.
 *
 * Pure: no file access. The caller reads the file and passes its text (null when there is none), then acts on
 * `action`: write the defaults, or keep the broken file as `backupName` first. A value of the wrong type falls back
 * to its default and is named in `notice`; unknown keys are dropped.
 *
 * One known difference from Python: JSON cannot tell 60 from 60.0 once parsed, so an integer field written as
 * «60.0» is accepted here and rejected by Python. Pulse itself never writes such a value.
 */

export const DEFAULT_GAME_DIR = "C:\\aMain\\Games\\AION Imperia\\Aion Empire";

/** Field -> default, in the order of the Python dataclass (config.json keeps this order). */
export const DEFAULTS = {
  game_dir: DEFAULT_GAME_DIR,
  chat_log: "",
  keywords: [] as string[],
  watch_items: [] as string[],
  history_min: 0,
  collapsed_groups: [] as string[],
  poll_interval_ms: 500,
  cooldown_sec: 60,
  sound_path: "",
  sound_volume: 80,
  alert_mode: "standard",
  search_mode: "or",
  react_sec: 30,
  remind_min: 5,
  remind_events: [] as string[],
  remind_last_check: "",
  nag_popup: false,
  show_counters: true,
  chat_minutes: 15,
  chat_system: false,
  filter_grades: [] as string[],
  filter_level_min: 0,
  filter_level_max: 0,
  items_width: 0,
  map_quests: true,
  map_hidden: ["rifts"] as string[],
  settings_open: false,
  map_side: "dark",
  game_check: true,
  filter_type: "",
  reduce_motion: false,
  notify_off: [] as string[],
  notify_mute: [] as string[],
  notify_dnd: false,
  notify_corner: "bottom",
  notify_duration: 8,
  notify_stack: 3,
  schedule_hidden: [] as string[],
  schedule_check: true,
  schedule_seen: "",
  update_check: true,
  update_seen: "",
};

export type Config = typeof DEFAULTS;
export type ConfigAction = "write_defaults" | "backup_and_write" | null;

export interface ReadResult {
  config: Config;
  notice: string;
  action: ConfigAction;
}

/** A fresh copy of the defaults (lists are not shared between configs). */
export function defaultConfig(): Config {
  return JSON.parse(JSON.stringify(DEFAULTS)) as Config;
}

/** True when a JSON value has the type of the field's default (a boolean is not a number here). */
export function validValue(value: unknown, fallback: unknown): boolean {
  if (typeof fallback === "boolean") return typeof value === "boolean";
  if (typeof fallback === "number") {
    if (typeof value !== "number") return false;
    return Number.isInteger(fallback) ? Number.isInteger(value) : true;
  }
  if (Array.isArray(fallback)) return Array.isArray(value) && value.every((item) => typeof item === "string");
  return typeof value === "string";
}

/**
 * Load config from the file's text. `text` null = no file; `backupName` names the copy a broken file is kept as
 * (the caller makes it, «config.json.broken-<time>»).
 */
export function readConfig(text: string | null, backupName = "config.json.broken"): ReadResult {
  if (text === null) return { config: defaultConfig(), notice: "", action: "write_defaults" };
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    data = undefined;
  }
  if (data === null || typeof data !== "object" || Array.isArray(data)) {
    return {
      config: defaultConfig(),
      notice: `config.json был повреждён, сохранён как ${backupName}; загружены настройки по умолчанию`,
      action: "backup_and_write",
    };
  }
  const config = defaultConfig() as Record<string, unknown>;
  const wrong: string[] = [];
  for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
    if (!(key in DEFAULTS)) continue;
    if (validValue(value, (DEFAULTS as Record<string, unknown>)[key])) config[key] = value;
    else wrong.push(key);
  }
  const notice = wrong.length
    ? "в config.json неверный тип у настроек: " + wrong.sort().join(", ") + "; взяты значения по умолчанию"
    : "";
  return { config: config as Config, notice, action: null };
}

/** The text of config.json (two-space indent, fields in the dataclass order, as Python writes it). */
export function serializeConfig(config: Config): string {
  const ordered: Record<string, unknown> = {};
  for (const key of Object.keys(DEFAULTS)) ordered[key] = (config as Record<string, unknown>)[key];
  return JSON.stringify(ordered, null, 2);
}

/** The game's chat log: the explicit path, or <game folder>\classic\Chat.log. */
export function chatLogPath(config: Config): string {
  if (config.chat_log) return config.chat_log;
  return `${config.game_dir.replace(/[\\/]+$/, "")}\\classic\\Chat.log`;
}
