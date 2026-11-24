// The state of the two updates (the program, the game data) shared by the notice at the bottom of the window and the
// settings panel: what is on offer, the progress, the error, «Позже». The checks and the installs are the ones the two
// header buttons used to do (UpdateButton, DbPackButton); nothing is downloaded without the user's click.
import { listen } from "@tauri-apps/api/event";
import { useSyncExternalStore } from "react";

import { REPO, offer, type Offer } from "../core/update/plus";
import { installOrder, isPostponed, pending, pendingKey, type Part, type Pending } from "../core/update/hub";
import { releaseApi } from "../core/update/updater";
import { platform } from "./platform";

const LATER = "pulse.update.later"; // the set of updates the user put off: its notice stays away, the buttons live in the settings
const APP_FIRST_MS = 5000;
const DB_FIRST_MS = 6000;
const APP_EVERY_MS = 6 * 3600 * 1000;

export interface UpdatesState {
  app: Offer | null;
  db: { size: number; built: string } | null;
  progress: { part: Part; done: number; total: number } | null;
  error: string;
  later: string;
}

const read = (): string => { try { return localStorage.getItem(LATER) ?? ""; } catch { return ""; } };
let state: UpdatesState = { app: null, db: null, progress: null, error: "", later: read() };
const listeners = new Set<() => void>();
const set = (patch: Partial<UpdatesState>) => { state = { ...state, ...patch }; listeners.forEach((fn) => fn()); };

export const offers = (s: UpdatesState): Pending | null => pending(s.app ? { tag: s.app.tag } : null, s.db);
/** The notice at the bottom shows while there is something on offer that the user has not put off (an install in progress keeps it). */
export const noticeWanted = (s: UpdatesState): boolean => {
  const p = offers(s);
  return p !== null && (s.progress !== null || !isPostponed(p, s.later));
};

export const useUpdates = (): UpdatesState => useSyncExternalStore((fn) => { listeners.add(fn); return () => { listeners.delete(fn); }; }, () => state);

let started = false;
let installing = false; // a check during an install does not replace what is being installed

async function checkApp() {
  try {
    const status = await platform!.updateStatus();
    const [body] = await platform!.httpFetch(releaseApi(REPO), "GET");
    const next = offer(body, status.version, "", status.can_install);
    if (!installing) set({ app: next });
  } catch { /* no network or GitHub busy: the next check */ }
}

async function checkDb() {
  try {
    const status = await platform!.dbPackStatus();
    if (status.available && status.can_install && !installing) set({ db: { size: status.size, built: status.built } });
  } catch { /* no answer: the database is as it is */ }
}

/** Starts the checks once (the program only; the plain browser has nothing to update). */
export function startUpdates() {
  if (started || !platform) return;
  started = true;
  setTimeout(checkApp, APP_FIRST_MS);
  setInterval(checkApp, APP_EVERY_MS);
  setTimeout(checkDb, DB_FIRST_MS);
}

/** «Позже»: the notice goes away for this set of updates, the buttons stay in the settings. */
export function postpone() {
  const p = offers(state);
  if (!p) return;
  const key = pendingKey(p);
  try { localStorage.setItem(LATER, key); } catch { /* the notice comes back next start */ }
  set({ later: key });
}

/** Installs the chosen parts in the safe order: data first (no restart), the program last (it restarts the program). */
export async function install(only?: Part) {
  const p = offers(state);
  if (!p || !platform || installing) return;
  const parts = installOrder(p).filter((part) => !only || part === only);
  installing = true;
  set({ error: "" });
  let dbDone = false;
  try {
    for (const part of parts) {
      if (part === "db") {
        set({ progress: { part, done: 0, total: state.db?.size ?? 0 } });
        const off = await listen<{ done: number; total: number }>("db-progress", (e) => set({ progress: { part, ...e.payload } }));
        try { await platform.dbPackInstall(); dbDone = true; set({ db: null }); } finally { off(); }
      } else if (state.app?.asset) {
        const asset = state.app.asset;
        set({ progress: { part, done: 0, total: asset.size } });
        const off = await listen<{ done: number; total: number }>("update-progress", (e) => set({ progress: { part, ...e.payload } }));
        try { await platform.updateInstall(asset.url, asset.size, asset.sha256); } finally { off(); } // the program closes on success
      }
    }
    if (dbDone) window.location.reload(); // every screen reads the new database from the start
  } catch (e) {
    const text = String(e).replace(/^Error:\s*/, "");
    set({ error: dbDone ? `${text}. Данные игры обновлены, перезапусти программу, чтобы увидеть их.` : text, progress: null });
  } finally {
    installing = false;
    if (state.progress && state.error) set({ progress: null });
  }
}

export const openReleasePage = () => { if (state.app && platform) platform.openUrl(state.app.page); };
