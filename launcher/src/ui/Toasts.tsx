import { Icon } from "./Icon";
import { IconClose } from "./icons";
import type { Toast } from "./useWatch";

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
  if (!toasts.length) return null;
  return (
    <div className="toasts" role="region" aria-label="Уведомления" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.note.id} className={`toast ${toast.note.kind}`}>
          {toast.icon && <Icon name={toast.icon} size={40} />}
          <div className="toast-body">
            <div className="toast-title"><b>{toast.note.title}</b>
              <button className="x" aria-label="Закрыть" onClick={() => onDismiss(toast)}><IconClose /></button></div>
            <div className="muted toast-text">{toast.note.text}</div>
            <div className="toast-actions">
              {toast.note.actions.some((a) => a.id === "accept") && (
                <button className="btn primary" onClick={() => onAccept(toast)}>Принять</button>)}
              {toast.note.actions.some((a) => a.id === "retry") && (
                <button className="btn primary" onClick={() => onRetry(toast)}>Проверить снова</button>)}
              {!toast.note.actions.some((a) => a.id === "retry") && (
                <button className="btn" onClick={() => onSnooze(toast)}>Через 5 мин</button>)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
