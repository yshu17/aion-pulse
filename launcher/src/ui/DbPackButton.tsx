// The game database (data/pulse.db) as a pack of its own (docs/ADR-003-pulse-db-replace.md, step 4): the program asks the
// release for the record of the newest pack a little after the start. When a newer one that this program can read is there,
// the header offers it; a click downloads it (progress on the button), checks it and puts it in place, and the page reloads to
// read it. Nothing is downloaded without the click: the pack is ~17 MB, the data of a patch, not a fix of the program. Only a
// program started from Pulse+.exe can put it in place; the developer's build has the files and never asks.
import { listen } from "@tauri-apps/api/event";
import { useEffect, useRef, useState } from "react";

import { platform } from "./platform";

const FIRST_MS = 6000;
const mb = (bytes: number) => (bytes / 1048576).toFixed(0);
const day = (built: string) => built.slice(0, 10).split("-").reverse().join(".");

export function DbPackButton() {
  const [offer, setOffer] = useState<{ size: number; built: string } | null>(null);
  const [progress, setProgress] = useState<[number, number] | null>(null);
  const [error, setError] = useState("");
  const busy = useRef(false);

  useEffect(() => {
    if (!platform) return;
    let alive = true;
    const timer = setTimeout(async () => {
      try {
        const status = await platform!.dbPackStatus();
        if (alive && status.available && status.can_install) setOffer({ size: status.size, built: status.built });
      } catch { /* no answer: the database is as it is */ }
    }, FIRST_MS);
    return () => { alive = false; clearTimeout(timer); };
  }, []);

  const install = async () => {
    if (!platform || busy.current) return;
    busy.current = true;
    setError("");
    setProgress([0, offer?.size ?? 0]);
    const off = await listen<{ done: number; total: number }>("db-progress", (e) => setProgress([e.payload.done, e.payload.total]));
    try {
      await platform.dbPackInstall();
      window.location.reload(); // every screen reads the new database from the start
    } catch (e) {
      setError(String(e).replace(/^Error:\s*/, ""));
      setProgress(null);
    } finally {
      off();
      busy.current = false;
    }
  };

  if (error) {
    return <button className="btn maps-btn warn" title={`Не удалось обновить данные игры: ${error}`} onClick={install}>Данные: повторить</button>;
  }
  if (progress) {
    const percent = progress[1] > 0 ? Math.min(100, Math.round((progress[0] / progress[1]) * 100)) : 0;
    return (
      <div className="maps-btn" role="progressbar" aria-label="Скачивание данных игры" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}
        title={`Данные игры скачиваются: ${mb(progress[0])} из ${mb(progress[1])} МБ. Потом страница перезагрузится.`}>
        <i style={{ width: `${percent}%` }} />
        <span>Данные {percent}%</span>
      </div>
    );
  }
  if (!offer) return null;
  return (
    <button className="btn maps-btn offer" onClick={install}
      title={`Есть новые данные игры от ${day(offer.built)} (${mb(offer.size)} МБ): предметы, задания, NPC. Нажми, чтобы скачать; программа перезагрузится.`}>
      Обновить данные
    </button>
  );
}
