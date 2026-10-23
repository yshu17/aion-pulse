import { useEffect, useRef, useState } from "react";

import { Icon } from "./Icon";
import { IconClose, IconExpand, IconSettings } from "./icons";
import { dragOverlay, fitHeight, keepPlace, loadLook, onState, OverlayLook, OverlayState, saveLook, sendAction, setKeepGameFocus } from "./overlayWindow";

/** The page of the overlay window: one line over the game (status, the event now or next, the time left) and the notifications. */
export function Overlay() {
  const [state, setState] = useState<OverlayState | null>(null);
  const [look, setLookValue] = useState<OverlayLook>(loadLook);
  const [menu, setMenu] = useState(false);
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

  useEffect(() => { // the menu closes on a press outside it or on Esc
    if (!menu) return;
    const off = (e: Event) => { if (!(e.target as HTMLElement).closest?.(".ov-menu, .ov-line")) setMenu(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setMenu(false); };
    window.addEventListener("pointerdown", off);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("pointerdown", off); window.removeEventListener("keydown", esc); };
  }, [menu]);

  const live = state?.watching && !state.problem;
  const note = !state ? "Подключаюсь…" : !state.watching ? "Не слежу" : state.problem ? "Нет Chat.log" : "";
  const running = state?.schedule.current ?? [];
  const shown = running[0] ?? state?.schedule.next ?? null; // the event that ends first, else the next one
  const isRunning = running.length > 0;
  return (
    <div className="overlay" ref={root} style={{ ["--ov-opacity" as string]: look.opacity }}>
      <div className="ov-line" tabIndex={0} role="group" aria-label="Накладка Pulse+" onMouseDown={dragOverlay}
        title={state?.problem || "Потяни, чтобы передвинуть. Правый клик: меню"}
        onContextMenu={(e) => { e.preventDefault(); setMenu(!menu); }}
        onKeyDown={(e) => { if ((e.target as HTMLElement).closest("button")) return; if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10") || e.key === "Enter") { e.preventDefault(); setMenu(!menu); } }}>
        <span className="dot" style={{ background: live ? "var(--success)" : "var(--warning)" }} />
        {note && <span className="muted">{note}</span>}
        {shown ? (
          <>
            <span className={`ov-sw t-${shown.tone}`} aria-hidden />
            <b className="name">{shown.name}</b>
            {isRunning ? <span className="ov-state going">идёт</span> : <span className="ov-state muted num">в {shown.from}</span>}
            {isRunning && running.length > 1 && <span className="muted">+{running.length - 1}</span>}
            <span className="spacer" />
            <span className="ov-left num"><span className="muted">{isRunning ? "ещё" : "через"}</span> <b>{shown.left}</b></span>
            {isRunning && shown.progress !== null && (
              <span className="ov-prog" role="progressbar" aria-label="Прошло" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(shown.progress * 100)}>
                <i className={`t-${shown.tone}`} style={{ transform: `scaleX(${Math.min(1, Math.max(0, shown.progress))})` }} />
              </span>
            )}
          </>
        ) : (
          <><span className="spacer" /><span className="muted">событий нет</span></>
        )}
        <button className={`ov-gear${menu ? " on" : ""}`} aria-label="Меню накладки" aria-expanded={menu} title="Прозрачность, фокус, развернуть"
          onClick={() => setMenu(!menu)}><IconSettings /></button>
      </div>
      {menu && (
        <div className="ov-menu" role="menu">
          <button role="menuitem" className="ov-item" onClick={() => sendAction({ kind: "expand" })}><IconExpand />Развернуть Pulse+</button>
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
