// The update of Pulse+ (core/update/plus.ts): five seconds after the start and then every six hours the program asks
// GitHub for the latest release. A newer one shows a button in the header; its card offers «Обновить сейчас» (download,
// SHA-256 check, restart — the Rust side's update_install) or the release page, and «Позже» hides this version.
// Nothing is downloaded without the user's click. The developer's build (not started from Pulse+.exe) only offers the page.
import { listen } from "@tauri-apps/api/event";
import { useCallback, useEffect, useRef, useState } from "react";

import { REPO, offer, type Offer } from "../core/update/plus";
import { releaseApi } from "../core/update/updater";
import { IconCheck } from "./icons";
import { Presence } from "./motion";
import { platform } from "./platform";
import { announce, useYields } from "./schedule/popover";

const SEEN = "pulse.update.seen"; // the version the user put off
const FIRST_MS = 5000;
const EVERY_MS = 6 * 3600 * 1000;

const seen = () => { try { return localStorage.getItem(SEEN) ?? ""; } catch { return ""; } };
const mb = (bytes: number) => (bytes / 1048576).toFixed(1).replace(".", ",");

export function UpdateButton() {
  const [found, setFound] = useState<Offer | null>(null);
  const [open, setOpen] = useState(false);
  const [progress, setProgress] = useState<[number, number] | null>(null);
  const [error, setError] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const installing = useRef(false); // a check during the download does not replace what is being installed
  const close = useCallback(() => setOpen(false), []);
  useYields("update", close);

  useEffect(() => {
    if (!platform) return;
    let alive = true;
    const check = async () => {
      try {
        const status = await platform!.updateStatus();
        const [body] = await platform!.httpFetch(releaseApi(REPO), "GET");
        const next = offer(body, status.version, seen(), status.can_install);
        if (alive && !installing.current) setFound(next);
      } catch { /* no network or GitHub busy: the next check */ }
    };
    const first = setTimeout(check, FIRST_MS);
    const every = setInterval(check, EVERY_MS);
    return () => { alive = false; clearTimeout(first); clearInterval(every); };
  }, []);

  useEffect(() => {
    if (!open) return;
    const outside = (e: Event) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape" && !progress) setOpen(false); };
    window.addEventListener("pointerdown", outside);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("pointerdown", outside); window.removeEventListener("keydown", esc); };
  }, [open, progress]);

  if (!found || !platform) return null;

  const install = async () => {
    if (!found.asset) return;
    setError("");
    setProgress([0, found.asset.size]);
    installing.current = true;
    const off = await listen<{ done: number; total: number }>("update-progress", (e) => setProgress([e.payload.done, e.payload.total]));
    try {
      await platform!.updateInstall(found.asset.url, found.asset.size, found.asset.sha256); // the program closes on success
    } catch (e) {
      setError(String(e).replace(/^Error:\s*/, ""));
      setProgress(null);
      installing.current = false;
    } finally {
      off();
    }
  };
  const later = () => {
    try { localStorage.setItem(SEEN, found.tag); } catch { /* the button comes back next start */ }
    setOpen(false);
    setFound(null);
  };
  const page = () => { platform!.openUrl(found.page); };
  const percent = progress && progress[1] > 0 ? Math.min(100, Math.round((progress[0] / progress[1]) * 100)) : 0;

  return (
    <div className="update" ref={root}>
      <button className={`btn update-btn${open ? " active" : ""}`} aria-expanded={open} aria-haspopup="dialog"
        title={`Доступна новая версия ${found.tag}`} onClick={() => { if (!open) announce("update"); setOpen(!open); }}>
        <span className="update-dot" aria-hidden="true" />Обновление<span className="label"> {found.tag}</span>
      </button>
      <Presence show={open}>
        <div className="update-pop" role="dialog" aria-label={`Pulse+ ${found.tag}`}>
          <b>Доступна новая версия {found.tag}</b>
          {found.asset
            ? <p className="muted">Pulse+ скачает Pulse+.exe с GitHub ({mb(found.asset.size)} МБ), проверит контрольную сумму SHA-256 и перезапустится.</p>
            : <p className="muted">Скачай новый Pulse+.exe со страницы релиза и запусти его вместо старого.</p>}
          {progress && (
            <div className="update-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
              <i style={{ width: `${percent}%` }} />
              <span>{percent < 100 ? `Скачиваю… ${mb(progress[0])} из ${mb(progress[1])} МБ` : <><IconCheck />Проверено, перезапускаю…</>}</span>
            </div>
          )}
          {error && <p className="update-error" role="alert">Не удалось обновить: {error}. Скачай файл со страницы релиза.</p>}
          <div className="r">
            {found.asset && !error && <button className="btn primary" disabled={!!progress} onClick={install}>Обновить сейчас</button>}
            <button className="btn" disabled={!!progress} onClick={page}>{found.asset && !error ? "Что нового" : "Открыть релиз"}</button>
            <button className="btn" disabled={!!progress} onClick={later}>Позже</button>
          </div>
        </div>
      </Presence>
    </div>
  );
}
