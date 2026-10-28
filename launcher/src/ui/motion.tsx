// Smooth leaving: what goes away stays on screen for a short fade, then is removed (see the «leave» rules in kit.css).
import { ReactNode, useEffect, useRef, useState } from "react";

export const LEAVE_MS = 160; // as --t-leave in theme.css

const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const leaveMs = () => (reduced() ? 0 : LEAVE_MS);

/**
 * Shows its children while `show`, and for a short fade after it turns off: the wrapper adds no box (display: contents),
 * only the class `leaving` the CSS fades by. Turning `show` on again during the fade brings them straight back.
 */
export function Presence({ show, children }: { show: boolean; children: ReactNode }) {
  const [mounted, setMounted] = useState(show);
  const last = useRef<ReactNode>(children);
  if (show) last.current = children;
  useEffect(() => {
    if (show) { setMounted(true); return; }
    const timer = setTimeout(() => setMounted(false), leaveMs());
    return () => clearTimeout(timer);
  }, [show]);
  if (!show && !mounted) return null;
  return <div className={`presence${show ? "" : " leaving"}`}>{show ? children : last.current}</div>;
}

/**
 * A list whose removed items stay a moment, marked `leaving`, so they fade out instead of vanishing; an item that comes
 * back during its fade simply stays.
 */
export function useLeaving<T>(items: T[], keyOf: (item: T) => string | number): { item: T; leaving: boolean }[] {
  const [gone, setGone] = useState<Map<string | number, { item: T; index: number }>>(new Map());
  const previous = useRef<T[]>(items);
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>()); // each fade ends on its own, even if the list changes again
  useEffect(() => () => { for (const t of timers.current) clearTimeout(t); }, []);
  useEffect(() => {
    const now = new Set(items.map(keyOf));
    const removed = previous.current.map((item, index) => ({ item, index })).filter(({ item }) => !now.has(keyOf(item)));
    previous.current = items;
    if (!removed.length) return;
    setGone((map) => { const next = new Map(map); for (const r of removed) next.set(keyOf(r.item), r); return next; });
    const timer = setTimeout(() => {
      timers.current.delete(timer);
      setGone((map) => { const next = new Map(map); for (const r of removed) next.delete(keyOf(r.item)); return next; });
    }, leaveMs());
    timers.current.add(timer);
  }, [items]); // eslint-disable-line react-hooks/exhaustive-deps -- keyOf is a plain accessor
  const live = new Set(items.map(keyOf));
  const out = items.map((item) => ({ item, leaving: false }));
  for (const [key, { item, index }] of gone) if (!live.has(key)) out.splice(Math.min(index, out.length), 0, { item, leaving: true });
  return out;
}
