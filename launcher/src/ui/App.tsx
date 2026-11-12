import { listen } from "@tauri-apps/api/event";
import { Suspense, lazy, useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import type { FeedMode } from "./chatRows";
import { Feed } from "./Feed";
import { IconBug, IconCheck, IconLeft, IconOverlay, IconPlay, IconReset, IconSettings, IconStop } from "./icons";
import { reportText } from "./bugReport";
import { copyText } from "./map/GatherPanel";
import { closeCardWindow, openCardWindow } from "./cardLink";
import { ItemCard, OpenCard, OpenItem } from "./ItemCard";
import { platform } from "./platform";
import { ItemsPanel } from "./ItemsPanel";
import { CardRef, ChatPlace, MapTarget, OpenMap, OpenPlace, OpenRef } from "./map/placeLink";
import { AnimatePresence } from "motion/react";
import { Glide, Pop } from "./fx";
import { SettingsPanel } from "./SettingsPanel";
import { enterOverlay, hidePopup, leaveOverlay, onAction, POPUP_HIDE_MS, POPUP_SHOW_MS, sendState, showPopup } from "./overlayWindow";
import { ScheduleTab } from "./schedule/ScheduleTab";
import { overlaySchedule } from "./schedule/overlaySchedule";
import { useSchedule } from "./schedule/useSchedule";
import { Toasts } from "./Toasts";
import { TopTabs } from "./TopTabs";
import { UpdateButton } from "./UpdateButton";
import { MapsButton } from "./MapsButton";
import { DbPackButton } from "./DbPackButton";
import { Credit } from "./Credit";
import { back, visit } from "../core/nav";
import { LIVE_TABS, tabLabel } from "../core/tabs";
import { Boot, useBoot } from "./useBoot";
import { useItems } from "./data";
import { useWatch } from "./useWatch";

const MODES: [string, string][] = [["or", "Слово или предмет"], ["words", "Только слова"], ["items", "Только предметы"], ["and", "Слово и предмет"]];

// the big screens come with their first opening: the chat, shown at the start, does not wait for the map's and the database's code
const MapTab = lazy(() => import("./map/MapTab").then((m) => ({ default: m.MapTab })));
const BestiaryTab = lazy(() => import("./bestiary/BestiaryTab").then((m) => ({ default: m.BestiaryTab })));
const DbTab = lazy(() => import("./db/DbTab").then((m) => ({ default: m.DbTab })));
const GearTab = lazy(() => import("./gear/GearTab").then((m) => ({ default: m.GearTab })));

/** One tab's place: all the opened tabs lie one on another, only the chosen one is seen (a hidden one keeps its size and scroll). */
function Pane({ on, children }: { on: boolean; children: ReactNode }) {
  return <div className={`pane${on ? " on" : ""}`} aria-hidden={!on}><Suspense fallback={<main className="soon"><p>Открываю…</p></main>}>{children}</Suspense></div>;
}

export default function App() {
  const boot = useBoot();
  const items = useItems(); // read alongside the settings
  if (!boot.ready || !items.ready) {
    return <div className="window loading"><span className="muted">{boot.ready ? "Загружаю предметы…" : "Загружаю настройки…"}</span></div>;
  }
  return <Screen boot={boot} itemsProblem={items.problem} />;
}


function Screen({ boot, itemsProblem }: { boot: Boot; itemsProblem: string }) {
  const notice = boot.notice || itemsProblem;
  const watch = useWatch(boot);
  const schedule = useSchedule(boot, watch.notify); // reminders come on every tab
  const problem = watch.source.kind === "missing" || watch.source.kind === "error";
  const [overlay, setOverlay] = useState(false);
  const gameOff = watch.game === false;
  // the toasts repeat the cards of the feed: while this window is in use they would only cover the item list
  const [focused, setFocused] = useState(() => document.hasFocus());
  useEffect(() => {
    const on = () => setFocused(true);
    const off = () => setFocused(false);
    window.addEventListener("focus", on);
    window.addEventListener("blur", off);
    return () => { window.removeEventListener("focus", on); window.removeEventListener("blur", off); };
  }, []);

  // notifications over the game: with the program window open (it may be under the game) they come in the overlay window
  const popupWanted = !overlay && boot.platform !== null && watch.toasts.length > 0;
  const popupShown = useRef(false);
  useEffect(() => {
    if (popupWanted) {
      popupShown.current = true;
      const timer = setTimeout(showPopup, POPUP_SHOW_MS); // after leaveOverlay has hidden the overlay, if that is what just happened
      return () => clearTimeout(timer);
    }
    if (popupShown.current) {
      popupShown.current = false;
      if (!overlay) { // the last toast fades out first; a new one in that time keeps the window
        const timer = setTimeout(hidePopup, POPUP_HIDE_MS);
        return () => clearTimeout(timer);
      }
    }
  }, [popupWanted, overlay]);

  useEffect(() => { // the overlay shows what this window would show
    if (!overlay && !popupWanted) return;
    sendState({
      watching: watch.watching, problem: problem ? watch.source.text : "", counters: watch.counters,
      toasts: watch.toasts.map((t) => ({ id: t.note.id, title: t.note.title, text: t.note.text, icon: t.icon, elapsed: performance.now() / 1000 - t.shownAt,
        accept: t.note.actions.some((a) => a.id === "accept"), retry: t.note.actions.some((a) => a.id === "retry") })),
      schedule: overlaySchedule(schedule.visible, schedule.now),
      game: watch.game,
      popup: !overlay,
    });
  }, [overlay, popupWanted, watch.watching, watch.counters, watch.toasts, watch.source, problem, schedule.visible, schedule.now, watch.game]);

  useEffect(() => { // the program started again: the running one comes back from the overlay (Rust shows this window)
    if (!boot.platform) return;
    const off = listen("pulse-show-main", () => setOverlay(false));
    return () => { off.then((unlisten) => unlisten()); };
  }, [boot.platform]);

  const live = useRef(watch); // the overlay's buttons act on the current state without re-subscribing every render
  live.current = watch;
  useEffect(() => {
    if (!boot.platform) return;
    const off = onAction((action) => {
      const watch = live.current;
      if (action.kind === "expand") { setOverlay(false); leaveOverlay(); return; }
      const toast = watch.toastById(action.id);
      if (!toast) return;
      if (action.kind === "accept") watch.acceptToast(toast);
      else if (action.kind === "retry") watch.retryToast(toast);
      else if (action.kind === "snooze") watch.snoozeToast(toast);
      else watch.dismissToast(toast);
    });
    return () => { off.then((unlisten) => unlisten()); };
  }, [boot.platform]);
  const [tab, setTab] = useState("Чат");
  // the way back: every move to another screen adds the one left to the trail; «Назад» returns to it (its place is kept: tabs stay alive)
  const [trail, setTrail] = useState<string[]>([]);
  const tabNow = useRef(tab);
  tabNow.current = tab;
  const go = useCallback((id: string) => {
    const from = tabNow.current;
    if (id === from) return;
    tabNow.current = id; // a link may move twice in one go (a tab, then its section)
    setTrail((t) => visit(t, from, id));
    setTab(id);
  }, []);
  const trailRef = useRef(trail);
  trailRef.current = trail;
  const goBack = useCallback(() => {
    const [to, rest] = back(trailRef.current);
    if (to === null) return;
    trailRef.current = rest;
    tabNow.current = to;
    setTrail(rest);
    setTab(to);
  }, []);
  useEffect(() => { // Alt+← and the mouse's «back» button
    const key = (e: KeyboardEvent) => { if (e.altKey && e.key === "ArrowLeft" && trailRef.current.length) { e.preventDefault(); goBack(); } };
    const mouse = (e: MouseEvent) => { if (e.button === 3 && trailRef.current.length) { e.preventDefault(); goBack(); } };
    window.addEventListener("keydown", key);
    window.addEventListener("mouseup", mouse);
    return () => { window.removeEventListener("keydown", key); window.removeEventListener("mouseup", mouse); };
  }, [goBack]);
  // A tab that has been opened stays alive under the others (hidden, same size): its chosen NPC, search, zone, scroll and
  // fields are what the user left when coming back. A tab not opened yet is not drawn at all.
  const [seen, setSeen] = useState<ReadonlySet<string>>(() => new Set(["Чат"]));
  useEffect(() => { setSeen((old) => (old.has(tab) ? old : new Set(old).add(tab))); }, [tab]);
  const alive = (name: string) => tab === name || seen.has(name);
  // every section of «База данных» is a screen of its own and stays alive like a tab: its filters, chosen row and scroll are kept
  const dbSections = [...seen].filter((name) => name.startsWith("db:"));
  const [feedMode, setFeedMode] = useState<FeedMode>("all");
  const [settings, setSettings] = useState(false);
  const [card, setCard] = useState<OpenCard | null>(null); // the item card opened from the chat
  const [mapHome, setMapHome] = useState(0); // «Карта» pressed again: back to Atreia
  // what the map is asked to show (a place of the chat, an NPC of a card): one way in, see placeLink.ts
  const [mapTarget, setMapTarget] = useState<(MapTarget & { n: number }) | null>(null);
  const openMap = useCallback((target: MapTarget) => {
    setMapTarget((old) => ({ ...target, n: (old?.n ?? 0) + 1 }));
    go("Карта");
  }, [go]);
  const openPlace = useCallback((place: ChatPlace) => openMap({ type: "place", ...place }), [openMap]);
  // a name in a card of «База данных» opens where it lives: an NPC in «NPC», a zone on the map, an item, a quest or a title in its section
  const [npcTarget, setNpcTarget] = useState<{ id: string; name: string; n: number } | null>(null);
  const [dbTarget, setDbTarget] = useState<(CardRef & { n: number; section: string }) | null>(null);
  const openRef = useCallback((ref: CardRef) => {
    if (ref.kind === "zone") { openMap({ type: "zone", map_id: ref.id }); return; }
    if (ref.kind === "npc") { setNpcTarget((old) => ({ id: ref.id, name: ref.name, n: (old?.n ?? 0) + 1 })); go("NPC"); return; }
    const section = `db:${{ item: "Предметы", quest: "Задания", title: "Титулы" }[ref.kind]}`;
    setDbTarget((old) => ({ ...ref, n: (old?.n ?? 0) + 1, section }));
    go(section);
  }, [openMap, go]);
  const closeCard = useCallback(() => setCard(null), []);
  // the program: the card is a window of its own (it may stand outside this one); the plain browser: inside the page
  const openCard = useCallback((open: OpenCard) => { if (platform) openCardWindow(open.id); else setCard(open); }, []);
  useEffect(() => { // the card's window goes with the chat: away from the tab or into the overlay, it hides
    if (platform && (tab !== "Чат" || overlay)) closeCardWindow();
  }, [tab, overlay]);
  useEffect(() => { // Esc here closes the card's window too (it has no focus while the chat is read)
    if (!platform) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") closeCardWindow(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);
  const [confirmReset, setConfirmReset] = useState(false);
  const [reported, setReported] = useState(false); // the bug button: the report went to the clipboard
  const [found, reacted, missed] = watch.counters;
  const cfg = boot.config;
  const modeText = MODES.find(([value]) => value === cfg.search_mode)?.[1] ?? "слово или предмет";
  const since = watch.since ? new Date(watch.since) : null;
  const sinceText = since ? `с ${since.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" })}, ${since.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}` : "за всё время";

  return (
    <div className="window">
      <header className="top">
        <span className="brand">Pulse<i>+</i></span>
        <button type="button" className="btn icon-only back" disabled={!trail.length} aria-label="Назад"
          title={trail.length ? `Назад: ${tabLabel(trail[trail.length - 1])} (Alt+←)` : "Назад: некуда"} onClick={goBack}><IconLeft /></button>
        <TopTabs tab={tab} onPick={(id) => { if (id === "Карта" && tab === "Карта") setMapHome((n) => n + 1); go(id); }} />
        <span className="spacer" />
        <DbPackButton />
        <MapsButton />
        <UpdateButton />
        <button className="btn" disabled={!boot.platform}
          title={boot.platform ? "Спрятать окно: поверх игры останутся полоса и уведомления" : "Только в программе"}
          aria-label="В накладку" onClick={() => { setOverlay(true); enterOverlay(); }}><IconOverlay /><span className="label">В накладку</span></button>
        <button className="btn icon-only" aria-label="Сообщить о ошибке" title="Сообщить о ошибке: данные для отчёта копируются в буфер обмена"
          onClick={() => { copyText(reportText({ tab, watching: watch.watching, chatLog: boot.chatLog })).then(() => { setReported(true); setTimeout(() => setReported(false), 2500); }); }}>
          {reported ? <IconCheck /> : <IconBug />}</button>
        <button className={`btn${settings ? " active" : ""}`} aria-label="Настройки" title="Настройки" aria-expanded={settings}
          onClick={() => setSettings(true)}><IconSettings /><span className="label">Настройки</span></button>
      </header>

      <div className="panes">
      <Pane on={tab === "Чат"}>
        <main className="chat">
          <div className="chat-head">
            <div className="head">
              {watch.watching
                ? <button className="go stop" onClick={() => watch.setWatching(false)}><IconStop />Стоп</button>
                : <button className="go start" onClick={() => watch.setWatching(true)}><IconPlay />Старт</button>}
              <div className={`live${problem || gameOff ? " warn" : !watch.watching ? " off" : ""}`} title={watch.source.text}>
                <b><span className="dot" />{gameOff ? "Игра не запущена" : !watch.watching ? "Не слежу" : problem ? "Нет Chat.log" : "Слежу"}</b>
                <span>{watch.source.kind === "demo" ? "демо-чат" : gameOff ? "запусти Aion и нажми «Старт»" : problem
                  ? "проверь папку игры в настройках" : watch.game ? "Chat.log · игра запущена" : "Chat.log"}</span>
              </div>
              <span className="sep" />
              <div className="count"><Pop value={found} /><span>найдено</span></div>
              <div className="count ok"><Pop value={reacted} /><span>принято</span></div>
              <div className="count no"><Pop value={missed} /><span>пропущено</span></div>
              <div className="reset-box">
                <button className="link" aria-expanded={confirmReset} onClick={() => setConfirmReset(true)}><IconReset />Сбросить</button>
                <span className="since">{sinceText}</span>
                {confirmReset && (
                  <div className="confirm" role="alertdialog" aria-label="Сбросить счётчики?">
                    <b>Сбросить счётчики?</b>
                    <div className="muted">{found} найдено, {reacted} принято, {missed} пропущено обнулятся. Отменить нельзя.</div>
                    <div className="r">
                      <button className="btn danger" onClick={() => { watch.reset(); setConfirmReset(false); }}>Сбросить</button>
                      <button className="btn" autoFocus onClick={() => setConfirmReset(false)}>Оставить</button>
                    </div>
                  </div>
                )}
              </div>
              <span className="spacer" />
              {feedMode === "all" && (
                <label className="check">
                  <input type="checkbox" checked={watch.system} onChange={(e) => watch.setSystem(e.target.checked)} />
                  <span className="box" /><span>Система</span>
                </label>
              )}
              <div className="segmented" role="radiogroup" aria-label="Что показывать">
                {([["all", "Весь чат"], ["matches", "Совпадения"]] as [FeedMode, string][]).map(([value, label]) => (
                  <button key={value} role="radio" aria-checked={feedMode === value} className={feedMode === value ? "on" : ""}
                    onClick={() => setFeedMode(value)}>{feedMode === value && <Glide group="seg-feed" />}<span>{label}</span></button>
                ))}
              </div>
            </div>
            <div className="what">
              Ищу:{cfg.keywords.length ? cfg.keywords.map((k) => <span key={k} className="kw">{k}</span>) : <span className="muted">слов нет</span>}
              <span>·</span><span className="mode-text">{modeText.toLowerCase()}</span>
              <button className="link accent" onClick={() => setSettings(true)}>изменить</button>
            </div>
          </div>
          <div className="search">
          <section className="card feed-card">
            {gameOff && (
              <div className="banner warn row">
                <span>Игра не запущена: слежение остановлено. Запусти Aion и нажми «Старт» или проверь снова.</span>
                <button className="btn" onClick={() => watch.checkGame().then((r) => { if (r !== false) watch.setWatching(true); })}>Проверить снова</button>
              </div>)}
            {(problem || notice) && <div className={`banner${problem ? " warn" : ""}`}>{problem ? watch.source.text : notice}</div>}
            <OpenItem.Provider value={openCard}>
              <OpenPlace.Provider value={openPlace}>
              <Feed rows={watch.rows} mode={feedMode} system={watch.system} reactSec={cfg.react_sec}
                alerts={{ state: watch.state, remaining: watch.remaining, onAccept: watch.accept }} />
              </OpenPlace.Provider>
            </OpenItem.Provider>
          </section>
          <OpenItem.Provider value={openCard}>
            <ItemsPanel checked={watch.checked} onChange={watch.setChecked} />
          </OpenItem.Provider>
          </div>
        </main>
      </Pane>
      {alive("Карта") && (
        <Pane on={tab === "Карта"}>
          <OpenMap.Provider value={openMap}>
            <MapTab boot={boot} target={mapTarget} home={mapHome} onPlaceCleared={() => setMapTarget(null)} />
          </OpenMap.Provider>
        </Pane>
      )}
      {alive("NPC") && (
        <Pane on={tab === "NPC"}>
          <OpenMap.Provider value={openMap}>
            <BestiaryTab target={npcTarget} />
          </OpenMap.Provider>
        </Pane>
      )}
      {alive("Расписание") && <Pane on={tab === "Расписание"}><ScheduleTab schedule={schedule} /></Pane>}
      {dbSections.map((section) => (
        <Pane key={section} on={tab === section}>
          <OpenMap.Provider value={openMap}>
            <OpenRef.Provider value={openRef}>
              <DbTab tab={section} onSection={go} target={dbTarget?.section === section ? dbTarget : null} />
            </OpenRef.Provider>
          </OpenMap.Provider>
        </Pane>
      ))}
      {alive("calc:Экипировка") && <Pane on={tab === "calc:Экипировка"}><GearTab /></Pane>}
      {!LIVE_TABS.includes(tab) && !tab.startsWith("db:") && tab !== "calc:Экипировка" && <main key={tab} className="soon"><p>Раздел «{tabLabel(tab)}» будет следующим.</p></main>}
      </div>
      <AnimatePresence>{card && tab === "Чат" && <ItemCard key="item-card" card={card} onClose={closeCard} />}</AnimatePresence>
      <AnimatePresence>{settings && <SettingsPanel key="settings" boot={boot} onClose={() => setSettings(false)} onTrySound={watch.playSound} />}</AnimatePresence>
      {boot.platform === null && !overlay && !focused && <Toasts toasts={watch.toasts} remaining={watch.remaining} onAccept={watch.acceptToast} onRetry={watch.retryToast}
        onSnooze={watch.snoozeToast} onDismiss={watch.dismissToast} />}
      <Credit />
    </div>
  );
}
