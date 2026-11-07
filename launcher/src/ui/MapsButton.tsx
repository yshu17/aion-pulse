// The map pictures (140 MB) are not in Pulse+.exe: they are a pack of their own that the program downloads when there are
// no maps yet (a new install) or when a map has changed — an update of the program does not carry them again. A few
// seconds after the start the program asks Rust (maps_status); when the pack is needed it comes in the background and the
// header shows the progress. Only a program started from Pulse+.exe does this; the developer's build has the files.
import { listen } from "@tauri-apps/api/event";
import { useEffect, useRef, useState } from "react";

import { mapsArrived } from "./map/mapData";
import { platform } from "./platform";

const FIRST_MS = 3000;
const mb = (bytes: number) => (bytes / 1048576).toFixed(0);

export function MapsButton() {
  const [progress, setProgress] = useState<[number, number] | null>(null); // [done, total] while the pack comes
  const [error, setError] = useState("");
  const [size, setSize] = useState(0);
  const busy = useRef(false);

  const install = async () => {
    if (!platform || busy.current) return;
    busy.current = true;
    setError("");
    setProgress([0, size]);
    const off = await listen<{ done: number; total: number }>("maps-progress", (e) => setProgress([e.payload.done, e.payload.total]));
    try {
      await platform.mapsInstall();
      mapsArrived(); // the map screens read their pictures again
      setProgress(null);
    } catch (e) {
      setError(String(e).replace(/^Error:\s*/, ""));
      setProgress(null);
    } finally {
      off();
      busy.current = false;
    }
  };

  useEffect(() => {
    if (!platform) return;
    let alive = true;
    const timer = setTimeout(async () => {
      try {
        const status = await platform!.mapsStatus();
        if (!alive || !status.needed) return;
        setSize(status.size);
        install();
      } catch { /* no status: the maps are as they are */ }
    }, FIRST_MS);
    return () => { alive = false; clearTimeout(timer); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <button className="btn maps-btn warn" title={`Не удалось скачать карты: ${error}`} onClick={install}>
        Карты: повторить
      </button>
    );
  }
  if (!progress) return null;
  const percent = progress[1] > 0 ? Math.min(100, Math.round((progress[0] / progress[1]) * 100)) : 0;
  return (
    <div className="maps-btn" role="progressbar" aria-label="Скачивание карт" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}
      title={`Карты игры скачиваются: ${mb(progress[0])} из ${mb(progress[1])} МБ. Они нужны для вкладки «Карта».`}>
      <i style={{ width: `${percent}%` }} />
      <span>Карты {percent}%</span>
    </div>
  );
}
