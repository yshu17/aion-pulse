import { useEffect } from "react";

/** One floating layer at a time: whatever opens says so, and every other layer closes itself. */
const EVENT = "sch-pop";

export const announce = (id: string) => window.dispatchEvent(new CustomEvent(EVENT, { detail: id }));

/** `close` runs when a layer other than `id` opens. */
export function useYields(id: string, close: () => void) {
  useEffect(() => {
    const on = (e: Event) => { if ((e as CustomEvent<string>).detail !== id) close(); };
    window.addEventListener(EVENT, on);
    return () => window.removeEventListener(EVENT, on);
  }, [id, close]);
}
