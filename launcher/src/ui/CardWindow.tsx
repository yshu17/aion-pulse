// The page of the item card's window: the card next to the click, kept inside the work area of that monitor (not of
// the program's window), as tall as its description; dragged by its title like any window, hidden by its cross or Esc.
import { PhysicalPosition, PhysicalSize } from "@tauri-apps/api/dpi";
import { currentMonitor, getCurrentWindow, monitorFromPoint } from "@tauri-apps/api/window";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { CardOpen, onCardClose, onCardOpen } from "./cardLink";
import { CardBody, OFFSET, useEsc, useSpec } from "./ItemCard";
import { useItems } from "./data";

const MARGIN = 8; // from the edges of the work area, CSS pixels

export function CardWindow() {
  const [open, setOpen] = useState<(CardOpen & { n: number }) | null>(null);
  const close = useCallback(() => {
    setOpen(null);
    getCurrentWindow().hide().catch(() => {});
  }, []);
  useEffect(() => {
    document.documentElement.classList.add("card-mode");
    const off = [onCardOpen((card) => setOpen((old) => ({ ...card, n: (old?.n ?? 0) + 1 }))), onCardClose(close)];
    return () => { off.forEach((p) => p.then((stop) => stop())); };
  }, [close]);
  useEsc(close);
  const items = useItems(); // the card's title and grade come from the catalog
  return open && items.ready ? <Placed key={open.n} open={open} onClose={close} /> : null;
}

/** One opening of the card: placed by its click, then kept on the screen when the description makes it taller. */
function Placed({ open, onClose }: { open: CardOpen; onClose(): void }) {
  const answer = useSpec(open.id);
  const root = useRef<HTMLDivElement>(null);
  const [maxHeight, setMaxHeight] = useState<number | null>(null); // CSS pixels: the work area's height
  const shown = useRef(false);

  const place = useCallback(async () => {
    const el = root.current;
    if (!el) return;
    const win = getCurrentWindow();
    const monitor = (await monitorFromPoint(open.x, open.y)) ?? (await currentMonitor());
    if (!monitor) return;
    const area = monitor.workArea;
    const ratio = window.devicePixelRatio; // CSS -> window pixels of this window
    const margin = Math.round(MARGIN * monitor.scaleFactor);
    const css = Math.floor((area.size.height - 2 * margin) / ratio);
    if (css !== maxHeight) { setMaxHeight(css); return; } // laid out again with the limit, then placed
    const width = Math.ceil(el.offsetWidth * ratio);
    const height = Math.ceil(el.offsetHeight * ratio);
    const right = area.position.x + area.size.width - margin;
    const bottom = area.position.y + area.size.height - margin;
    const keep = (x: number, y: number) => ({
      x: Math.min(Math.max(area.position.x + margin, x), right - width),
      y: Math.min(Math.max(area.position.y + margin, y), bottom - height),
    });
    let at;
    if (!shown.current) { // right of the click, left when there is no room on this monitor
      const offset = Math.round(OFFSET * monitor.scaleFactor);
      const x = open.x + offset + width <= right ? open.x + offset : open.x - offset - width;
      at = keep(x, open.y - Math.round(20 * monitor.scaleFactor));
    } else {
      const now = await win.outerPosition();
      at = keep(now.x, now.y);
    }
    await win.setSize(new PhysicalSize(width, height));
    await win.setPosition(new PhysicalPosition(at.x, at.y));
    if (!shown.current) { shown.current = true; await win.show(); }
  }, [open, maxHeight]);
  useLayoutEffect(() => { place(); }, [place, answer]);

  return <CardBody id={open.id} answer={answer} onClose={onClose} className="in-window" cardRef={root}
    style={maxHeight ? { maxHeight } : undefined}
    onDrag={() => { getCurrentWindow().startDragging().catch(() => {}); }} />;
}
