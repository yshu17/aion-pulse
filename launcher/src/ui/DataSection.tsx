// «Настройки → Данные»: the database and the map packs of the releases — what is installed, what is newer, download the
// chosen ones or all (core/update/dataPacks.ts). Nothing is downloaded without a click; the database goes last, as the
// page reloads to read it.
import { listen } from "@tauri-apps/api/event";
import { useCallback, useEffect, useState } from "react";

import { allWanted, packRows, selectedSize, summaryText, type PackId, type PackRow, type PackState } from "../core/update/dataPacks";
import { IconCheck } from "./icons";
import { mapsArrived } from "./map/mapData";
import { platform } from "./platform";

const BADGE: Record<PackState, string> = { ok: "установлено", newer: "есть новее", missing: "не скачано", unknown: "нет ответа", fixed: "в папке программы" };
const mb = (bytes: number) => (bytes / 1048576).toLocaleString("ru-RU", { maximumFractionDigits: 1 });

export function DataSection() {
  const [rows, setRows] = useState<PackRow[] | null>(null);
  const [chosen, setChosen] = useState<PackId[]>([]);
  const [progress, setProgress] = useState<{ id: PackId; percent: number } | null>(null);
  const [error, setError] = useState("");
  const check = useCallback(async () => {
    if (!platform) return;
    setRows(null);
    try {
      const [db, maps] = await Promise.all([platform.dbPackStatus(), platform.mapsStatus()]);
      const next = packRows(db, maps);
      setRows(next);
      setChosen(allWanted(next));
    } catch (e) {
      setRows([]);
      setError(String(e).replace(/^Error:\s*/, ""));
    }
  }, []);
  useEffect(() => { check(); }, [check]);

  const download = async (ids: PackId[]) => {
    if (!platform || progress) return;
    setError("");
    try {
      for (const id of (["maps", "db"] as PackId[]).filter((x) => ids.includes(x))) {
        setProgress({ id, percent: 0 });
        const off = await listen<{ done: number; total: number }>(id === "maps" ? "maps-progress" : "db-progress",
          (e) => setProgress({ id, percent: e.payload.total > 0 ? Math.min(100, Math.round((e.payload.done / e.payload.total) * 100)) : 0 }));
        try {
          if (id === "maps") { await platform.mapsInstall(); mapsArrived(); }
          else { await platform.dbPackInstall(); window.location.reload(); } // every screen reads the new database from the start
        } finally { off(); }
      }
      setProgress(null);
      check();
    } catch (e) {
      setProgress(null);
      setError(String(e).replace(/^Error:\s*/, ""));
    }
  };

  const wanted = rows ? allWanted(rows) : [];
  const size = rows ? selectedSize(rows, chosen) : 0;
  return (
    <section className="sec data-packs">
      <h3>Данные</h3>
      {!platform ? <div className="hint">Только в программе: в браузере скачивать нечего.</div> : !rows ? <div className="hint">Проверяю релизы на GitHub…</div> : <>
        <div className="hint">Что скачивается из релизов на GitHub. Можно взять только нужное.</div>
        {rows.map((r) => {
          const can = r.state === "newer" || r.state === "missing";
          const body = <>
            <span className="nm">{r.name} <em className={r.state}>{BADGE[r.state]}</em></span>
            <span className="size">{r.size ? `${mb(r.size)} МБ` : ""}</span>
            <span className="note">{r.note}</span>
            {progress?.id === r.id && <span className="bar" role="progressbar" aria-label={`Скачивание: ${r.name}`} aria-valuenow={progress.percent} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${progress.percent}%` }} /></span>}
          </>;
          // a checkbox only where there is something to choose; elsewhere a mark of the state in the same column
          return can ? (
            <label key={r.id} className="data-pack can">
              <input type="checkbox" disabled={!!progress} checked={chosen.includes(r.id)}
                onChange={(e) => setChosen((c) => (e.target.checked ? [...c, r.id] : c.filter((x) => x !== r.id)))} />
              {body}
            </label>
          ) : (
            <div key={r.id} className="data-pack">
              <span className={`mark ${r.state}`} aria-hidden>{r.state === "ok" ? <IconCheck /> : "–"}</span>
              {body}
            </div>
          );
        })}
        {wanted.length > 0 && <div className="data-acts">
          <button type="button" className="btn" disabled={!!progress} onClick={() => download(wanted)}>Скачать всё</button>
          <button type="button" className="btn primary" disabled={!!progress || !size} onClick={() => download(chosen)}>
            {progress ? `Скачивается… ${progress.percent}%` : size ? `Скачать выбранное · ${mb(size)} МБ` : "Ничего не выбрано"}</button>
        </div>}
        <div className="data-foot">
          <span>{summaryText(rows)}</span>
          <button type="button" className="data-again" disabled={!!progress} onClick={() => { setError(""); check(); }}>Проверить снова</button>
        </div>
        {error && <div className="data-error" role="alert">Не удалось: {error}. Уже установленное не тронуто.</div>}
      </>}
    </section>
  );
}
