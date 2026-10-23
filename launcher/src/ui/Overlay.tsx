import { useEffect, useRef, useState } from "react";

import { Icon } from "./Icon";
import { IconClose, IconExpand } from "./icons";
import { dragOverlay, fitHeight, keepPlace, onState, OverlayEvent, OverlayState, sendAction } from "./overlayWindow";

/** The page of the overlay window: a status strip and the notifications, over the game. */
export function Overlay() {
  const [state, setState] = useState<OverlayState | null>(null);
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
    <div className="overlay" ref={root}>
      <div className="strip" title={state?.problem || "Потяни, чтобы передвинуть"} onMouseDown={dragOverlay}>
        <span className="dot" style={{ background: live ? "var(--success)" : "var(--warning)" }} />
        <span>{!state ? "Подключаюсь…" : !state.watching ? "Не слежу" : state.problem ? "Нет Chat.log" : "Слежу"}</span>
        <span className="muted">{found} · {reacted} · {missed}</span>
        <span className="spacer" />
        <button className="btn mini-plain" onClick={() => sendAction({ kind: "expand" })}><IconExpand />Развернуть</button>
      </div>
      {state && (state.schedule.current.length > 0 || state.schedule.next) && (
        <div className="ov-schedule" onMouseDown={dragOverlay} title="Потяни, чтобы передвинуть">
          {state.schedule.current.length > 0
            ? state.schedule.current.map((e, i) => <Row key={e.name + e.from} label={i === 0 ? "Сейчас" : ""} event={e} time={`до ${e.to}`} />)
            : <div className="ov-row"><span className="lbl">Сейчас</span><span className="muted">ничего нет</span></div>}
          {state.schedule.next && <Row label="Дальше" event={state.schedule.next} time={state.schedule.next.from} />}
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

function Row({ label, event, time }: { label: string; event: OverlayEvent; time: string }) {
  return (
    <div className="ov-row">
      <span className="lbl">{label}</span>
      <span className={`ov-dot t-${event.tone}`} />
      <b className="name">{event.name}</b>
      <span className="when">{time} <span className="left">{event.left}</span></span>
    </div>
  );
}
