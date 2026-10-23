// The bridge to the computer: files through the Tauri commands of src-tauri/src/lib.rs. In a plain browser (the dev
// page, tests) there are no files: `platform` is null and the screens run on demo data.
import { invoke } from "@tauri-apps/api/core";

export interface Platform {
  configPath(): Promise<string>;
  /** Is the game process running? null when the process list cannot be read. */
  gameRunning(): Promise<boolean | null>;
  /** config.json files near the launcher where an old Pulse may keep its settings, nearest first. */
  pulseConfigCandidates(): Promise<string[]>;
  /** The text of a file, or null when it does not exist. */
  readText(path: string): Promise<string | null>;
  /** Only inside the launcher's config folder (the Rust side refuses any other place). */
  writeText(path: string, text: string): Promise<void>;
  /** A missing file rejects with an error whose `code` is "ENOENT". */
  fileSize(path: string): Promise<number>;
  readRange(path: string, position: number, length: number): Promise<Uint8Array>;
  /** GET or HEAD of an address on the server's sites (aionempire.com / .net) (the Rust side refuses others): [text, headers]. */
  httpFetch(url: string, method: "GET" | "HEAD"): Promise<[string, Record<string, string>]>;
  /** An address in the default browser. */
  openUrl(url: string): Promise<void>;
}

/** Rust errors are texts; «ENOENT: …» becomes an error with that code, as the log reader of the core expects. */
function fileError(error: unknown): Error {
  const text = String(error);
  const failure = new Error(text) as Error & { code?: string };
  if (text.startsWith("ENOENT")) failure.code = "ENOENT";
  return failure;
}

async function call<T>(command: string, args: Record<string, unknown> = {}): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw fileError(error);
  }
}

const tauri: Platform = {
  configPath: () => call("config_path"),
  gameRunning: () => call("game_running"),
  pulseConfigCandidates: () => call("pulse_config_candidates"),
  readText: (path) => call("read_text", { path }),
  writeText: (path, text) => call("write_text", { path, text }),
  fileSize: (path) => call("file_size", { path }),
  readRange: async (path, position, length) => new Uint8Array(await call<ArrayBuffer>("read_range", { path, position, length })),
  httpFetch: (url, method) => call("http_fetch", { url, method }),
  openUrl: async (url) => { const { openUrl } = await import("@tauri-apps/plugin-opener"); await openUrl(url); },
};

export const platform: Platform | null = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window ? tauri : null;
