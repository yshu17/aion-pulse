import { useEffect, useRef, useState } from "react";

import type { FeedMode } from "./chatRows";
import { Feed } from "./Feed";
import { IconCheck, IconOverlay, IconPause, IconPlay, IconSettings } from "./icons";
import { ItemsPanel } from "./ItemsPanel";
import { enterOverlay, leaveOverlay, onAction, sendState } from "./overlayWindow";
import { Toasts } from "./Toasts";
import { Boot, useBoot } from "./useBoot";
import { useWatch } from "./useWatch";

const TABS = ["Чат", "Карта", "NPC / Бестиарий", "Расписание", "Крафт", "Броня", "Стигмы", "Гайды"];
const MODES: [string, string][] = [["or", "Слово ИЛИ предмет"], ["words", "Только слова"], ["items", "Только предметы"], ["and", "Слово И предмет"]];

export default function App() {
  const boot = useBoot();
  if (!boot.ready) return <div className="window loading"><span className="muted">Загружаю настройки…</span></div>;
  return <Screen boot={boot} />;
}

function Screen({ boot }: { boot: Boot }) {
  const watch = useWatch(boot);
  const problem = watch.source.kind === "missing" || watch.source.kind === "error";
  const [overlay, setOverlay] = useState(false);

  useEffect(() => { // the overlay shows what this window would show
    if (!overlay) return;
    sendState({
      watching: watch.watching, problem: problem ? watch.source.text : "", counters: watch.counters,
      toasts: watch.toasts.map((t) => ({ id: t.note.id, title: t.note.title, text: t.note.text, icon: t.icon,
        accept: t.note.actions.some((a) => a.id === "accept") })),
    });
  }, [overlay, watch.watching, watch.counters, watch.toasts, watch.source, problem]);

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
      else if (action.kind === "snooze") watch.snoozeToast(toast);
      else watch.dismissToast(toast);
    });
    return () => { off.then((unlisten) => unlisten()); };
  }, [boot.platform]);
  const [tab, setTab] = useState("Чат");
  const [feedMode, setFeedMode] = useState<FeedMode>("matches");
  const [pausedAt, setPausedAt] = useState<number | null>(null);
  const lastKey = watch.rows.length ? watch.rows[watch.rows.length - 1].key : 0;
  const held = pausedAt === null ? 0 : watch.rows.filter((r) => r.key > pausedAt && (r.entry || r.category || (watch.system && r.notice))).length;
  const [found, reacted, missed] = watch.counters;

  return (
    <div className="window">
      <header className="top">
        <h1>Pulse</h1>
        <span className="muted">Поиск группы</span>
        <span className="spacer" />
        <span className="stat"><i style={{ background: "var(--text)" }} /><b>{found}</b> найдено</span>
        <span className="stat"><i style={{ background: "var(--success)" }} /><b>{reacted}</b> отреагировал</span>
        <span className="stat"><i style={{ background: "var(--danger)" }} /><b>{missed}</b> пропущено</span>
        <button className="link" onClick={watch.reset}>Сбросить</button>
      </header>

      <div className="bar">
        {watch.watching
          ? <button className="btn stop" onClick={() => watch.setWatching(false)}>Stop</button>
          : <button className="btn start" onClick={() => watch.setWatching(true)}>Start</button>}
        <span className={`btn status${watch.watching && !problem ? " on" : ""}${problem ? " warn" : ""}`} title={watch.source.text}>
          {watch.watching && !problem && <IconCheck />}
          {!watch.watching ? "Не слежу" : problem ? "Нет Chat.log" : watch.source.kind === "demo" ? "Слежу · демо" : "Слежу"}
        </span>
        <label className="keywords">
          <span className="muted">Ключевые слова</span>
          <input className="field" value={watch.keywords} onChange={(e) => watch.setKeywords(e.target.value)}
            aria-label="Ключевые слова" />
        </label>
        <select className="field mode" value={watch.mode} onChange={(e) => watch.setMode(e.target.value)} aria-label="Режим поиска">
          {MODES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <button className="btn" disabled={!boot.platform}
          title={boot.platform ? "Спрятать окно: поверх игры останутся полоса и уведомления" : "Только в программе"}
          onClick={() => { setOverlay(true); enterOverlay(); }}><IconOverlay />В накладку</button>
        <button className="btn"><IconSettings />Настройки</button>
      </div>

      <nav className="tabs" role="tablist">
        {TABS.map((name) => (
          <button key={name} role="tab" aria-selected={tab === name} className={`tab${tab === name ? " on" : ""}`}
            onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {tab === "Чат" ? (
        <main className="search">
          <section className="card feed-card">
            <div className="feed-bar">
              <div className="segmented" role="radiogroup" aria-label="Что показывать">
                {([["matches", "Совпадения"], ["all", "Весь чат"]] as [FeedMode, string][]).map(([value, label]) => (
                  <button key={value} role="radio" aria-checked={feedMode === value} className={feedMode === value ? "on" : ""}
                    onClick={() => setFeedMode(value)}>{label}</button>
                ))}
              </div>
              <span className="spacer" />
              {feedMode === "all" && (
                <label className="check">
                  <input type="checkbox" checked={watch.system} onChange={(e) => watch.setSystem(e.target.checked)} />
                  <span className="box" /><span>Система</span>
                </label>
              )}
              <button className={`btn${pausedAt !== null ? " held" : ""}`} aria-pressed={pausedAt !== null}
                onClick={() => setPausedAt(pausedAt === null ? lastKey : null)}>
                {pausedAt === null ? <><IconPause />Пауза</> : <><IconPlay />Продолжить{held ? ` · ${held}` : ""}</>}
              </button>
            </div>
            {(problem || boot.notice) && <div className={`banner${problem ? " warn" : ""}`}>{problem ? watch.source.text : boot.notice}</div>}
            <Feed rows={watch.rows} mode={feedMode} system={watch.system} pausedAt={pausedAt}
              alerts={{ state: watch.state, remaining: watch.remaining, onAccept: watch.accept }} />
          </section>
          <ItemsPanel checked={watch.checked} onChange={watch.setChecked} />
        </main>
      ) : (
        <main className="soon"><p>Вкладка «{tab}» будет следующей.</p></main>
      )}
      {!overlay && <Toasts toasts={watch.toasts} remaining={watch.remaining} onAccept={watch.acceptToast}
        onSnooze={watch.snoozeToast} onDismiss={watch.dismissToast} />}
    </div>
  );
}
