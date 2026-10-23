import { useEffect, useRef, useState } from "react";

import { Icon } from "./Icon";
import { IconClose, IconExpand, IconSettings } from "./icons";
import { dragOverlay, fitHeight, keepPlace, loadLook, onState, OverlayEvent, OverlayLook, OverlayState, saveLook, sendAction, setKeepGameFocus } from "./overlayWindow";

/** The page of the overlay window: a status strip and the notifications, over the game. */
export function Overlay() {
  const [state, setState] = useState<OverlayState | null>(null);
  const [look, setLookValue] = useState<OverlayLook>(loadLook);
  const [tuning, setTuning] = useState(false);
  const setLook = (next: OverlayLook) => { setLookValue(next); saveLook(next); };
  useEffect(() => { setKeepGameFocus(look.keepGameFocus); }, [look.keepGameFocus]);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.documentElement.classList.add("overlay-mode");
    const off = onState(setState);
    const moved = keepPlace();
    return () => { off.then((unlisten) => unlisten()); moved.then((unlisten) => unlisten()); };
  }, []);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const observer = new ResizeObserver(() => fitHeight(el.getBoundingClientRect().height + 2));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const [found, reacted, missed] = state?.counters ?? [0, 0, 0];
  const live = state?.watching && !state.problem;
  return (
    <div className="overlay" ref={root} style={{ ["--ov-opacity" as string]: look.opacity }}>
      <div className="strip" title={state?.problem || "Потяни, чтобы передвинуть"} onMouseDown={dragOverlay}>
        <span className="dot" style={{ background: live ? "var(--success)" : "var(--warning)" }} />
        <span>{!state ? "Подключаюсь…" : !state.watching ? "Не слежу" : state.problem ? "Нет Chat.log" : "Слежу"}</span>
        <span className="muted">{found} · {reacted} · {missed}</span>
        <span className="spacer" />
        <button className={`btn mini-plain icon${tuning ? " on" : ""}`} aria-label="Вид накладки" aria-expanded={tuning} title="Прозрачность и фокус"
          onClick={() => setTuning(!tuning)}><IconSettings /></button>
        <button className="btn mini-plain" onClick={() => sendAction({ kind: "expand" })}><IconExpand />Развернуть</button>
      </div>
      {tuning && (
        <div className="ov-tune">
          <label className="ov-opacity">
            <span>Прозрачность</span>
            <input type="range" min={30} max={100} step={5} value={Math.round(look.opacity * 100)} aria-valuetext={`${Math.round(look.opacity * 100)} %`}
              onChange={(e) => setLook({ ...look, opacity: Number(e.target.value) / 100 })} />
            <b>{Math.round(look.opacity * 100)} %</b>
          </label>
          <label className="ov-check">
            <input type="checkbox" checked={look.keepGameFocus} onChange={(e) => setLook({ ...look, keepGameFocus: e.target.checked })} />
            <span>Не забирать фокус у игры: после клика можно сразу писать в игре</span>
          </label>
        </div>
      )}
      {state && (state.schedule.current.length > 0 || state.schedule.next) && (
        <div className="ov-schedule" onMouseDown={dragOverlay} title="Потяни, чтобы передвинуть" aria-label="Расписание">
          {state.schedule.current.length > 0
            ? state.schedule.current.map((e) => <Row key={e.name + e.from} event={e} running />)
            : <div className="ov-row idle"><span className="muted">Сейчас событий нет</span></div>}
          {state.schedule.next && <Row event={state.schedule.next} running={false} />}
        </div>
      )}
      {state?.toasts.map((toast) => (
        <div key={toast.id} className="toast">
          {toast.icon && <Icon name={toast.icon} size={40} />}
          <div className="toast-body">
            <div className="toast-title"><b>{toast.title}</b>
              <button className="x" aria-label="Закрыть" onClick={() => sendAction({ kind: "dismiss", id: toast.id })}><IconClose /></button></div>
            <div className="muted toast-text">{toast.text}</div>
            <div className="toast-actions">
              {toast.accept && <button className="btn primary" onClick={() => sendAction({ kind: "accept", id: toast.id })}>Принять</button>}
              {toast.retry && <button className="btn primary" onClick={() => sendAction({ kind: "retry", id: toast.id })}>Проверить снова</button>}
              {!toast.retry && <button className="btn" onClick={() => sendAction({ kind: "snooze", id: toast.id })}>Через 5 мин</button>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function Row({ event, running }: { event: OverlayEvent; running: boolean }) {
  return (
    <div className={`ov-row ${running ? "now" : "next"}`}>
      <span className={`ov-mark t-${event.tone}`} aria-hidden />
      <div className="ov-main">
        <b className="name">{event.name}</b>
        <span className="sub">{running ? `идёт до ${event.to}` : `дальше, в ${event.from}`}</span>
      </div>
      <span className="ov-left">{running ? <>ещё <b>{event.left}</b></> : <>через <b>{event.left}</b></>}</span>
      {running && event.progress !== null && (
        <span className="ov-bar" role="progressbar" aria-label="Прошло" aria-valuemin={0} aria-valuemax={100}
          aria-valuenow={Math.round(event.progress * 100)}>
          <i className={`t-${event.tone}`} style={{ transform: `scaleX(${Math.min(1, Math.max(0, event.progress))})` }} />
        </span>
      )}
    </div>
  );
}
