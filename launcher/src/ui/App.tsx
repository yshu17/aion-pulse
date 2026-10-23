import { listen } from "@tauri-apps/api/event";
import { useEffect, useRef, useState } from "react";

import type { FeedMode } from "./chatRows";
import { Feed } from "./Feed";
import { IconOverlay, IconPlay, IconReset, IconSettings, IconStop } from "./icons";
import { ItemsPanel } from "./ItemsPanel";
import { SettingsPanel } from "./SettingsPanel";
import { enterOverlay, leaveOverlay, loadLook, onAction, sendState } from "./overlayWindow";
import { ScheduleTab } from "./schedule/ScheduleTab";
import { overlaySchedule } from "./schedule/overlaySchedule";
import { useSchedule } from "./schedule/useSchedule";
import { Toasts } from "./Toasts";
import { Boot, useBoot } from "./useBoot";
import { useWatch } from "./useWatch";

const TABS = ["Чат", "Карта", "NPC / Бестиарий", "Расписание", "Крафт", "Броня", "Стигмы", "Гайды"];
const MODES: [string, string][] = [["or", "Слово или предмет"], ["words", "Только слова"], ["items", "Только предметы"], ["and", "Слово и предмет"]];

export default function App() {
  const boot = useBoot();
  if (!boot.ready) return <div className="window loading"><span className="muted">Загружаю настройки…</span></div>;
  return <Screen boot={boot} />;
}

const GAME_GONE_MS = 15_000; // the game must be gone this long (three checks) before the overlay goes back

function Screen({ boot }: { boot: Boot }) {
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

  useEffect(() => { // the overlay shows what this window would show
    if (!overlay) return;
    sendState({
      watching: watch.watching, problem: problem ? watch.source.text : "", counters: watch.counters,
      toasts: watch.toasts.map((t) => ({ id: t.note.id, title: t.note.title, text: t.note.text, icon: t.icon,
        accept: t.note.actions.some((a) => a.id === "accept"), retry: t.note.actions.some((a) => a.id === "retry") })),
      schedule: overlaySchedule(schedule.visible, schedule.now),
      game: watch.game,
    });
  }, [overlay, watch.watching, watch.counters, watch.toasts, watch.source, problem, schedule.visible, schedule.now, watch.game]);

  useEffect(() => { // the game is closed for a while: the overlay is no more use, the main window comes back
    if (!overlay || watch.game !== false || !loadLook().returnWhenGameClosed) return;
    const timer = setTimeout(() => { setOverlay(false); leaveOverlay(); }, GAME_GONE_MS);
    return () => clearTimeout(timer); // the game is back (or the check failed): nothing to do
  }, [overlay, watch.game]);

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
  const [feedMode, setFeedMode] = useState<FeedMode>("matches");
  const [settings, setSettings] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [found, reacted, missed] = watch.counters;
  const cfg = boot.config;
  const modeText = MODES.find(([value]) => value === cfg.search_mode)?.[1] ?? "слово или предмет";
  const since = watch.since ? new Date(watch.since) : null;
  const sinceText = since ? `с ${since.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" })}, ${since.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}` : "за всё время";

  return (
    <div className="window">
      <header className="top">
        <span className="brand">Pulse<i>+</i></span>
        <nav className="tabs" role="tablist">
          {TABS.map((name) => (
            <button key={name} role="tab" aria-selected={tab === name} className={`tab${tab === name ? " on" : ""}`}
              onClick={() => setTab(name)}>{name}</button>
          ))}
        </nav>
        <span className="spacer" />
        <button className="btn" disabled={!boot.platform}
          title={boot.platform ? "Спрятать окно: поверх игры останутся полоса и уведомления" : "Только в программе"}
          aria-label="В накладку" onClick={() => { setOverlay(true); enterOverlay(); }}><IconOverlay /><span className="label">В накладку</span></button>
        <button className={`btn${settings ? " active" : ""}`} aria-label="Настройки" title="Настройки" aria-expanded={settings}
          onClick={() => setSettings(true)}><IconSettings /><span className="label">Настройки</span></button>
      </header>

      {tab === "Чат" ? (
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
              <div className="count"><b>{found}</b><span>найдено</span></div>
              <div className="count ok"><b>{reacted}</b><span>принято</span></div>
              <div className="count no"><b>{missed}</b><span>пропущено</span></div>
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
                {([["matches", "Совпадения"], ["all", "Весь чат"]] as [FeedMode, string][]).map(([value, label]) => (
                  <button key={value} role="radio" aria-checked={feedMode === value} className={feedMode === value ? "on" : ""}
                    onClick={() => setFeedMode(value)}>{label}</button>
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
            {(problem || boot.notice) && <div className={`banner${problem ? " warn" : ""}`}>{problem ? watch.source.text : boot.notice}</div>}
            <Feed rows={watch.rows} mode={feedMode} system={watch.system} reactSec={cfg.react_sec}
              alerts={{ state: watch.state, remaining: watch.remaining, onAccept: watch.accept }} />
          </section>
          <ItemsPanel checked={watch.checked} onChange={watch.setChecked} />
          </div>
        </main>
      ) : tab === "Расписание" ? (
        <ScheduleTab schedule={schedule} />
      ) : (
        <main className="soon"><p>Вкладка «{tab}» будет следующей.</p></main>
      )}
      {settings && <SettingsPanel boot={boot} onClose={() => setSettings(false)} onTrySound={watch.playSound} />}
      {!overlay && !focused && <Toasts toasts={watch.toasts} remaining={watch.remaining} onAccept={watch.acceptToast} onRetry={watch.retryToast}
        onSnooze={watch.snoozeToast} onDismiss={watch.dismissToast} />}
    </div>
  );
}
