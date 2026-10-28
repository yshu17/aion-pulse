import { getCurrentWindow } from "@tauri-apps/api/window";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { Icon } from "./Icon";
import { AnimatePresence, m } from "motion/react";

import { FADE } from "./fx";
import { Presence, useLeaving } from "./motion";
import { IconClose, IconExpand, IconSettings } from "./icons";
import { anchorOf, chooseSide, Side, windowOrigin } from "./overlayPlacement";
import { clipWindow, loadLook, onPlace, onState, onWindowMoved, OverlayEvent, OverlayLook, OverlayState, placeWindow, Point, saveAnchor, saveLook, sendAction, setKeepGameFocus, startDrag, windowPosition, workArea } from "./overlayWindow";

const STRIP_CSS = 36; // the height of the strip when it is not drawn (a popup of notifications)
const RAISE_MS = 3000; // how often the window is put above other always-on-top windows (a game can take the top place)
const SETTLE_MS = 250; // the strip stays this long after the last move before the side of the notifications is chosen
const OWN_MOVE_MS = 400; // moves reported this soon after the page placed its window are its own, not the user's
const NO_TOASTS: OverlayState["toasts"] = [];
const WIDTH_CSS = 380; // the overlay window's width (overlayWindow.ts)
const CARD_OUT_MS = 320; // the card fades out this long before the clip shrinks (kit.css)
const HOVER_MS = 1500; // the mouse rests this long on the strip before the card with the full names opens
const DRAG_PX = 4; // the mouse must move this far with the button down before the window is dragged; less is a click

/** The page of the overlay window: one line over the game (status, the event now or next, the time left) and the notifications. */
export function Overlay() {
  const [state, setState] = useState<OverlayState | null>(null);
  const [look, setLookValue] = useState<OverlayLook>(loadLook);
  const [menu, setMenu] = useState(false);
  const [turn, setTurn] = useState(0); // which of several running events the line shows now
  const [card, setCard] = useState(false); // the mouse rests on the strip: the card with the full names is open
  const hover = useRef<ReturnType<typeof setTimeout>>(undefined);
  const press = useRef<{ x: number; y: number } | null>(null); // where the button went down, until it becomes a drag
  const dragged = useRef(false);
  const setLook = (next: OverlayLook) => { setLookValue(next); saveLook(next); };
  useEffect(() => { setKeepGameFocus(look.keepGameFocus); }, [look.keepGameFocus]);
  const root = useRef<HTMLDivElement>(null);
  const pill = useRef<HTMLDivElement>(null);
  const gameRunning = useRef(false); // read by place(): the strip is free to move while the game runs
  gameRunning.current = state?.game === true;
  const [side, setSide] = useState<Side>("down"); // notifications and the menu open below the strip, or above it near the screen bottom
  const sideRef = useRef<Side>("down");
  const [edge, setEdge] = useState<"left" | "right">("right"); // the screen edge the strip is nearer to
  const anchor = useRef<Point | null>(null); // the strip's top-left corner on the screen: it stays put whatever opens around it
  const placedAt = useRef(0);
  const settle = useRef<ReturnType<typeof setTimeout>>(undefined);

  /** Where the strip is inside the window now (CSS pixels): below the notifications when they open upwards. */
  const inside = () => {
    const r = pill.current?.getBoundingClientRect();
    if (r) return { left: r.left, top: r.top };
    // a popup of notifications has no strip: its corner is the top of the window, or the bottom when they open upwards
    const height = root.current?.getBoundingClientRect().height ?? 0;
    return { left: 1, top: sideRef.current === "up" ? Math.max(1, height - 1) : 1 };
  };

  const cardShown = useRef(false); // read by clip(): the hover card is part of what is shown
  const cardEl = useRef<HTMLDivElement>(null);
  const unclip = useRef<ReturnType<typeof setTimeout>>(undefined);

  /**
   * The window is always as tall as the page with the hover card in it, so the card never waits for a resize; the part
   * of the window that is shown (and takes the mouse) is clipped to what is visible: the strip, the menu, notifications,
   * and the card only while it is open.
   */
  const clip = () => {
    const parts = [...(root.current?.querySelectorAll<HTMLElement>(".ov-line, .ov-menu, .toast") ?? [])];
    const boxes = parts.map((p) => p.getBoundingClientRect()).filter((r) => r.height > 0).map((r) => ({ top: r.top - 1, bottom: r.bottom + 1 }));
    // the card by its place in the layout, not its rect: read during its small slide, the rect is a few pixels off and
    // the clip would cut its border; a few pixels of room around it
    const card = cardEl.current, page = root.current;
    if (cardShown.current && card && page) {
      const top = page.getBoundingClientRect().top + card.offsetTop - page.offsetTop;
      boxes.push({ top: top - 8, bottom: top + card.offsetHeight + 8 });
    }
    if (!boxes.length) return;
    clipWindow(Math.min(...boxes.map((r) => r.top)), Math.max(...boxes.map((r) => r.bottom)));
  };
  const placing = useRef(false); // one placement at a time: a newer request waits and then uses the newest content
  const again = useRef(false);

  /**
   * Put the window where the anchor says, as tall as the content: the strip does not move when the card, the menu or
   * notifications open. The anchor is only the user's: a window pushed off a screen edge for a moment (a tall card)
   * does not move it, only the strip alone pushed off the taskbar does.
   */
  const place = () => {
    const el = root.current, at = anchor.current;
    if (!el || !at) return;
    if (placing.current) { again.current = true; return; }
    placing.current = true;
    const dpr = window.devicePixelRatio;
    const height = el.getBoundingClientRect().height;
    // where the strip will be in the resized window. Opening upwards, the page sits on the window's bottom edge (app.css),
    // so the strip is always 1 px above it: a whole pixel, the same with or without the card, nothing shifts by a fraction
    const windowCss = Math.max(36, Math.ceil((height + 2) * dpr)) / dpr;
    const offset = sideRef.current === "up"
      ? { left: inside().left, top: windowCss - 1 - (pill.current?.getBoundingClientRect().height ?? 0) }
      : inside();
    const origin = windowOrigin(at, offset, dpr);
    placedAt.current = performance.now();
    // with the game running the strip can go anywhere; without it the work area keeps it above the taskbar
    placeWindow(origin.x, origin.y, height + 2, !gameRunning.current)
      .then((placed) => {
        const alone = !el.querySelector(".ov-menu, .toast"); // only the strip shows (the hidden card does not count)
        if (alone && (placed.x !== origin.x || placed.y !== origin.y)) anchor.current = anchorOf(placed, offset, dpr);
      })
      .catch(() => {})
      .finally(() => {
        placedAt.current = performance.now();
        clip();
        placing.current = false;
        if (again.current) { again.current = false; place(); }
      });
  };

  /** Choose the side from the strip's place on its monitor: near the bottom of the screen the notifications open upwards. */
  const chooseAndPlace = async () => {
    const at = anchor.current;
    if (!at) return;
    const area = await workArea();
    if (area) {
      const middle = at.x + (WIDTH_CSS * window.devicePixelRatio) / 2;
      setEdge(middle < area.x + area.width / 2 ? "left" : "right");
      const stripHeight = (pill.current?.getBoundingClientRect().height ?? STRIP_CSS) * window.devicePixelRatio;
      const next = chooseSide(at.y, stripHeight, area.y, area.height, sideRef.current);
      if (next !== sideRef.current) { sideRef.current = next; setSide(next); return; } // the layout effect below places it
    }
    place();
  };

  useEffect(() => {
    document.documentElement.classList.add("overlay-mode");
    const off = onState(setState);
    const placed = onPlace((point) => { anchor.current = point; chooseAndPlace(); }); // «В накладку»: where to open
    const moved = onWindowMoved((x, y) => { // the user dragged the window: the strip's new place is kept
      if (performance.now() - placedAt.current < OWN_MOVE_MS) return;
      anchor.current = anchorOf({ x, y }, inside(), window.devicePixelRatio);
      saveAnchor(anchor.current);
      clearTimeout(settle.current);
      settle.current = setTimeout(chooseAndPlace, SETTLE_MS); // the side is chosen when the drag has stopped
    });
    windowPosition().then((pos) => { // the first place: where the window is now
      if (anchor.current) return;
      anchor.current = anchorOf(pos, inside(), window.devicePixelRatio);
      chooseAndPlace();
    }).catch(() => {});
    return () => {
      off.then((unlisten) => unlisten()); placed.then((unlisten) => unlisten()); moved.then((unlisten) => unlisten());
      clearTimeout(settle.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- the handlers read refs

  useLayoutEffect(() => { place(); }, [side]); // eslint-disable-line react-hooks/exhaustive-deps

  // the game is gone: the taskbar is back, the strip left over it (or under it) moves up into the work area
  useEffect(() => { if (state && state.game !== true) place(); }, [state?.game]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const observer = new ResizeObserver(() => place());
    observer.observe(el);
    return () => observer.disconnect();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { // a game can take the top place among always-on-top windows: put the overlay above it again
    const timer = setInterval(() => {
      const win = getCurrentWindow();
      win.isVisible().then((visible) => { if (visible) win.setAlwaysOnTop(true).catch(() => {}); }).catch(() => {});
    }, RAISE_MS);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => { // the menu closes on a press outside it or on Esc
    if (!menu) return;
    const off = (e: Event) => { if (!(e.target as HTMLElement).closest?.(".ov-menu, .ov-line")) setMenu(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setMenu(false); };
    window.addEventListener("pointerdown", off);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("pointerdown", off); window.removeEventListener("keydown", esc); };
  }, [menu]);

  const running = state?.schedule.current ?? [];
  const next = state?.schedule.next ?? null;
  // what the line cycles through: the events running now, then what starts next (when something runs)
  const slides: { event: OverlayEvent; running: boolean }[] = [
    ...running.map((event) => ({ event, running: true })),
    ...(next ? [{ event: next, running: false }] : []),
  ];
  const several = slides.length > 1;
  useEffect(() => { // events that overlap take turns on the line; a click on it (turn changes) starts the wait again
    if (!several) return;
    const timer = setTimeout(() => setTurn((t) => t + 1), look.turnSec * 1000);
    return () => clearTimeout(timer);
  }, [several, turn, look.turnSec]);

  const toasts = useLeaving(state?.toasts ?? NO_TOASTS, (t) => t.id);
  const popup = state?.popup === true; // only the notifications: the program window is open
  const live = state?.watching && !state.problem;
  // the strip shows the state only by the dot; the words are in its hint and in the card shown on hover
  const status = !state ? "Подключаюсь…" : !state.watching ? "Не слежу" : state.problem ? "Нет Chat.log" : "Слежу за чатом";
  const current = several ? turn % slides.length : 0; // the slide that is shown
  // the card opens after a short rest on the strip (not while it is dragged or the menu is open), closes when the mouse leaves
  const shown = card && !menu;
  useEffect(() => { // open: the clip grows first, then the card fades in; closed: it fades out, then the clip shrinks
    clearTimeout(unclip.current);
    cardShown.current = shown;
    if (shown) clip();
    else unclip.current = setTimeout(clip, CARD_OUT_MS);
    return () => clearTimeout(unclip.current);
  }, [shown]); // eslint-disable-line react-hooks/exhaustive-deps -- clip reads refs
  const rest = () => { clearTimeout(hover.current); hover.current = setTimeout(() => setCard(true), HOVER_MS); };
  const leave = () => { clearTimeout(hover.current); setCard(false); };
  useEffect(() => () => clearTimeout(hover.current), []);
  return (
    <div className={`overlay ${side} edge-${edge}`} ref={root} style={{ ["--ov-opacity" as string]: look.opacity }} onMouseLeave={leave}>
      {!popup && (
      <>
      <div className="ov-line" ref={pill} tabIndex={0} role="group" aria-label="Накладка Pulse+" 
        onMouseEnter={rest}
        onPointerDown={(e) => { leave(); dragged.current = false; press.current = e.button === 0 && !(e.target as HTMLElement).closest("button") ? { x: e.clientX, y: e.clientY } : null; }}
        onPointerMove={(e) => {
          const from = press.current;
          if (!from || !(e.buttons & 1) || Math.hypot(e.clientX - from.x, e.clientY - from.y) < DRAG_PX) return;
          press.current = null; dragged.current = true; startDrag();
        }}
        onPointerUp={() => { press.current = null; }} onPointerLeave={() => { press.current = null; }}
        onContextMenu={(e) => { e.preventDefault(); setMenu(!menu); }}
        onKeyDown={(e) => { if ((e.target as HTMLElement).closest("button")) return; if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10") || e.key === "Enter") { e.preventDefault(); setMenu(!menu); } }}>
        <span className="dot" role="img" aria-label={status} title={status} style={{ background: live ? "var(--success)" : "var(--warning)" }} />
        <div className={`ov-body${several ? " turns" : ""}`} aria-live="polite" onClick={() => { if (several && !dragged.current) setTurn((t) => t + 1); }}>
          <AnimatePresence initial={false} mode="popLayout">
          {slides.length > 0 ? slides.filter((_, i) => i === current).map(({ event: e, running: now }) => (
            <m.div key={(now ? "now " : "next ") + e.name + e.from} className="ov-slide on" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={FADE}>
              <span className={`ov-sw t-${e.tone}`} aria-hidden />
              <b className="name">{e.name}</b>
              {several && <span className="muted num" title="Идёт несколько событий и показано, что дальше: строка меняет их по очереди и по щелчку">{current + 1}/{slides.length}</span>}
              <span className="spacer" />
              <span className="ov-left num"><span className="muted">{now ? "ещё" : "через"}</span> <b>{e.left}</b></span>
              {now && e.progress !== null && (
                <span className="ov-prog" role="progressbar" aria-label="Прошло" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(e.progress * 100)}>
                  <i className={`t-${e.tone}`} style={{ transform: `scaleX(${Math.min(1, Math.max(0, e.progress))})` }} />
                </span>
              )}
            </m.div>
          )) : (
            <div className="ov-slide on"><span className="spacer" /><span className="muted">событий нет</span></div>
          )}
          </AnimatePresence>
        </div>
        {/* the two icon buttons: no card and no tooltip over them (their names are for screen readers) */}
        <div className="ov-tools" onMouseEnter={leave} onMouseLeave={rest}>
          <button className="ov-gear" aria-label="Развернуть Pulse+" onClick={() => sendAction({ kind: "expand" })}><IconExpand /></button>
          <button className={`ov-gear${menu ? " on" : ""}`} aria-label="Меню накладки: прозрачность и фокус" aria-expanded={menu}
            onClick={() => setMenu(!menu)}><IconSettings /></button>
        </div>
      </div>
      <Presence show={menu}>
        <div className="ov-menu" role="menu">
          <label className="ov-opacity">
            <span>Прозрачность</span>
            <input type="range" min={30} max={100} step={5} value={Math.round(look.opacity * 100)} aria-valuetext={`${Math.round(look.opacity * 100)} %`}
              onChange={(e) => setLook({ ...look, opacity: Number(e.target.value) / 100 })} />
            <b>{Math.round(look.opacity * 100)} %</b>
          </label>
          <label className="ov-opacity" title="Если идёт несколько событий, строка по очереди показывает каждое. Щелчок по строке меняет событие сразу.">
            <span>Смена событий</span>
            <input type="range" min={2} max={20} step={1} value={look.turnSec} aria-valuetext={`каждые ${look.turnSec} с`}
              onChange={(e) => setLook({ ...look, turnSec: Number(e.target.value) })} />
            <b>{look.turnSec} с</b>
          </label>
          <label className="ov-check">
            <input type="checkbox" checked={look.keepGameFocus} onChange={(e) => setLook({ ...look, keepGameFocus: e.target.checked })} />
            <span>Не забирать фокус у игры: после клика можно сразу писать в игре</span>
          </label>
        </div>
      </Presence>
      </>
      )}
      {toasts.map(({ item: toast, leaving }) => (
        <div key={toast.id} className={`toast${leaving ? " leaving" : ""}`}>
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
      {/* the hover card: drawn in advance, hidden by the clip and its opacity until the mouse rests on the strip */}
      {!popup && (
        <div ref={cardEl} className={`ov-card${shown ? " shown" : ""}`} role="tooltip" aria-hidden={!shown}>
          {slides.map(({ event: e, running: now }) => (
            <div key={(now ? "now " : "next ") + e.name + e.from} className="ov-card-row">
              <span className={`ov-sw t-${e.tone}`} aria-hidden />
              <b>{e.name}</b>
              <span className="ov-left num"><span className="muted">{now ? "ещё" : "через"}</span> <b>{e.left}</b></span>
            </div>
          ))}
          {slides.length === 0 && <div className="muted">Событий нет</div>}
          <div className="ov-card-status muted"><span className="dot" style={{ background: live ? "var(--success)" : "var(--warning)" }} />{state?.problem || status}</div>
          <div className="ov-card-hint">{several ? "Щелчок: следующее событие. " : ""}Потяни, чтобы передвинуть. Правый клик: меню.</div>
        </div>
      )}
    </div>
  );
}
