/**
 * The version of data/pulse.db this program reads (docs/ADR-003-pulse-db-replace.md): the one place that names it.
 *
 *   DB_SCHEMA                    core/pulse_db/build.py SCHEMA_VERSION (PRAGMA user_version); tests keep the two equal
 *   schemaState(found) -> state  whether a database of that version fits, and what to tell the user when it does not
 *   readSchema(all) -> state     the same, read from the database
 *
 * An older database lacks tables and columns the screens ask for: it does not fit. A newer one is read as it is: the
 * build only adds to the schema within a major line (a removal or a rename raises DB_SCHEMA_MAX on purpose).
 */

import type { All } from "./npcPoints";

export const DB_SCHEMA = 9;
/** The newest version known to stay readable; a database above it is still tried, with a warning. */
export const DB_SCHEMA_MAX = 9;

export interface SchemaState { found: number | null; fits: boolean; text: string }

export function schemaState(found: number | null): SchemaState {
  if (found === null) return { found, fits: false, text: "Не удалось прочитать версию базы игры." };
  if (found < DB_SCHEMA) {
    return { found, fits: false, text: `База игры старая: версия ${found}, программе нужна ${DB_SCHEMA}. Замените файл data/pulse.db новым или обновите программу.` };
  }
  if (found > DB_SCHEMA_MAX) {
    return { found, fits: true, text: `База игры новее программы: версия ${found}, программа знает ${DB_SCHEMA_MAX}. Если что-то не открывается, обновите программу.` };
  }
  return { found, fits: true, text: "" };
}

export async function readSchema(all: All): Promise<SchemaState> {
  try {
    const [row] = await all("PRAGMA user_version");
    const found = Number(row?.user_version);
    return schemaState(Number.isFinite(found) ? found : null);
  } catch {
    return schemaState(null);
  }
}
