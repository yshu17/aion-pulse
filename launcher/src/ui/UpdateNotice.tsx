// The updates, two places (state: ./updates.ts, wording and order: core/update/hub.ts):
//  - UpdateNotice: a card bottom-centre of the window when there is something to update — «Обновить», «Что нового», «Позже»;
//  - UpdateRows: the same buttons as rows at the top of the settings; «Позже» moves them there for good.
import { AnimatePresence, m } from "motion/react";
import { useEffect } from "react";

import { allLabel, announceText } from "../core/update/hub";
import { IconCheck } from "./icons";
import { FADE } from "./fx";
import { install, noticeWanted, offers, openReleasePage, postpone, startUpdates, useUpdates, type UpdatesState } from "./updates";

const mb = (bytes: number) => (bytes / 1048576).toFixed(1).replace(".", ",");
const day = (built: string) => built.slice(0, 10).split("-").reverse().join(".");

function Progress({ s }: { s: UpdatesState }) {
  if (!s.progress) return null;
  const { part, done, total } = s.progress;
  const percent = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
  const what = part === "db" ? "данные игры" : "программу";
  return (
    <div className="update-bar" role="progressbar" aria-label={`Скачивание: ${what}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
      <i style={{ width: `${percent}%` }} />
      <span>{percent < 100 ? `Скачиваю ${what}… ${mb(done)} из ${mb(total)} МБ` : <><IconCheck />Проверено{part === "app" ? ", перезапускаю…" : ""}</>}</span>
    </div>
  );
}

export function UpdateNotice() {
  const s = useUpdates();
  useEffect(() => { startUpdates(); }, []);
  const p = offers(s);
  const show = noticeWanted(s) && p !== null;
  return (
    <AnimatePresence>
      {show && p && (
        <m.div key="update-notice" className="update-notice" role="region" aria-label="Обновления" aria-live="polite"
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 24 }} transition={FADE}>
          <b>{announceText(p)}</b>
          {p.app && !s.app?.asset && <p className="muted">Скачай новый Pulse+.exe со страницы релиза и запусти его вместо старого.</p>}
          <Progress s={s} />
          {s.error && <p className="update-error" role="alert">Не удалось обновить: {s.error}</p>}
          <div className="r">
            {(s.app?.asset || s.db) && !s.error && <button className="btn primary" disabled={!!s.progress} onClick={() => install()}>{allLabel(p)}</button>}
            {p.app && <button className="btn" disabled={!!s.progress} onClick={openReleasePage}>{s.app?.asset && !s.error ? "Что нового" : "Открыть релиз"}</button>}
            <button className="btn" disabled={!!s.progress} onClick={postpone}>Позже</button>
          </div>
        </m.div>
      )}
    </AnimatePresence>
  );
}

/** The top of the settings: one row per update and the joint button; nothing when there is nothing to update. */
export function UpdateRows() {
  const s = useUpdates();
  const p = offers(s);
  if (!p) return null;
  const can = !s.progress;
  return (
    <section className="sec update-rows">
      <h3>Обновления</h3>
      {p.app && (
        <div className="update-row">
          <span className="t"><b>Программа {p.app.tag}</b><span>{s.app?.asset ? `Pulse+.exe, ${mb(s.app.asset.size)} МБ; после загрузки программа перезапустится` : "Скачай Pulse+.exe со страницы релиза"}</span></span>
          {s.app?.asset && <button className="btn" disabled={!can} onClick={() => install("app")}>Обновить</button>}
          <button className="btn" disabled={!can} onClick={openReleasePage}>Что нового</button>
        </div>
      )}
      {p.db && (
        <div className="update-row">
          <span className="t"><b>Данные игры от {day(p.db.built)}</b><span>{mb(p.db.size)} МБ: предметы, задания, NPC; потом страница перезагрузится</span></span>
          <button className="btn" disabled={!can} onClick={() => install("db")}>Обновить</button>
        </div>
      )}
      <Progress s={s} />
      {s.error && <p className="update-error" role="alert">Не удалось обновить: {s.error}</p>}
      {p.app && p.db && s.app?.asset && <div className="update-row"><button className="btn primary" disabled={!can} onClick={() => install()}>{allLabel(p)}</button></div>}
    </section>
  );
}
