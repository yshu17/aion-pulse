import { useEffect, useRef, useState } from "react";

import { Icon } from "./Icon";
import { IconClose, IconExpand } from "./icons";
import { fitHeight, onState, OverlayState, sendAction } from "./overlayWindow";

/** The page of the overlay window: a status strip and the notifications, over the game. */
export function Overlay() {
  const [state, setState] = useState<OverlayState | null>(null);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.documentElement.classList.add("overlay-mode");
    const off = onState(setState);
    return () => { off.then((unlisten) => unlisten()); };
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
      <div className="strip" title={state?.problem || undefined}>
        <span className="dot" style={{ background: live ? "var(--success)" : "var(--warning)" }} />
        <span>{!state ? "Подключаюсь…" : !state.watching ? "Не слежу" : state.problem ? "Нет Chat.log" : "Слежу"}</span>
        <span className="muted">{found} · {reacted} · {missed}</span>
        <span className="spacer" />
        <button className="btn mini-plain" onClick={() => sendAction({ kind: "expand" })}><IconExpand />Развернуть</button>
      </div>
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
