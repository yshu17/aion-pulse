import { Icon } from "./Icon";
import { IconCheck, IconClose } from "./icons";
import { AnimatePresence, m } from "motion/react";
import { useState } from "react";
import { TOAST_SHOWN_SEC, type Toast } from "./useWatch";

const SOFT = [0.22, 1, 0.36, 1] as const; // a toast eases in and settles slowly
/** The motion of a toast, the same in the window and in the overlay: it eases in from the side, leaves fading the same way,
 *  and the others glide to their new places (layout) instead of jumping. */
export const TOAST_ENTER = { opacity: { duration: 0.45, ease: SOFT }, x: { duration: 0.5, ease: SOFT }, scale: { duration: 0.5, ease: SOFT } };
// leaving: the toast fades in place (its room stays until it is gone), then the others glide into that room
export const TOAST_EXIT = { duration: 0.35, ease: [0.4, 0, 0.2, 1] as const };
export const TOAST_LAYOUT = { duration: 0.45, ease: SOFT };
export const TOAST_FROM = 40; // px from the screen edge a toast comes in from

/** The time left of a toast: the bar drains over TOAST_SHOWN_SEC; `elapsed` is read once, at mount. */
export function ToastTime({ elapsed }: { elapsed: number }) {
  const [passed] = useState(elapsed);
  return (
    <span className="toast-time" role="progressbar" aria-label="Осталось до закрытия" aria-valuemin={0} aria-valuemax={TOAST_SHOWN_SEC}
      aria-valuenow={Math.max(0, Math.round(TOAST_SHOWN_SEC - passed))}>
      <i style={{ animationDuration: `${TOAST_SHOWN_SEC}s`, animationDelay: `-${Math.max(0, passed)}s` }} />
    </span>
  );
}

interface Props {
  toasts: Toast[];
  remaining: Record<number, number>;
  onAccept(toast: Toast): void;
  onRetry(toast: Toast): void;
  onSnooze(toast: Toast): void;
  onDismiss(toast: Toast): void;
}

/** The notification stack: bottom-right of the window for now; the same cards go to an overlay window later. */
export function Toasts({ toasts, onAccept, onRetry, onSnooze, onDismiss }: Props) {
  // Motion: a card slides in, the others move aside smoothly (layout), a closed one slides out
  return (
    <div className="toasts" role="region" aria-label="Уведомления" aria-live="polite">
      <AnimatePresence initial={false}>
      {toasts.map((toast) => (
        <m.div key={toast.note.id} className={`toast motion ${toast.note.kind}`} layout
          initial={{ opacity: 0, x: TOAST_FROM, scale: 0.96 }} animate={{ opacity: 1, x: 0, scale: 1, transition: TOAST_ENTER }}
          exit={{ opacity: 0, x: TOAST_FROM * 0.6, scale: 0.98, transition: TOAST_EXIT }} transition={{ layout: TOAST_LAYOUT }}>
          {toast.icon && <Icon name={toast.icon} size={40} />}
          <div className="toast-body">
            <div className="toast-title"><b>{toast.note.title}</b>
              <button className="x" aria-label="Закрыть" onClick={() => onDismiss(toast)}><IconClose /></button></div>
            <div className="muted toast-text">{toast.note.text}</div>
            <div className="toast-actions">
              <button className="btn primary" onClick={() => onAccept(toast)}><IconCheck />Принять</button>
              {toast.note.actions.some((a) => a.id === "retry") && (
                <button className="btn" onClick={() => onRetry(toast)}>Проверить снова</button>)}
              {!toast.note.actions.some((a) => a.id === "retry") && (
                <button className="btn" onClick={() => onSnooze(toast)}>Через 5 мин</button>)}
            </div>
          </div>
          <ToastTime elapsed={performance.now() / 1000 - toast.shownAt} />
        </m.div>
      ))}
      </AnimatePresence>
    </div>
  );
}
