import { useState } from "react";

import { Feed } from "./Feed";
import { ItemsPanel } from "./ItemsPanel";
import { Toasts } from "./Toasts";
import { useWatch } from "./useWatch";

const TABS = ["Поиск", "Весь чат", "Карта", "NPC / Бестиарий", "Расписание", "Крафт", "Броня", "Стигмы", "Гайды"];
const MODES: [string, string][] = [["or", "Слово ИЛИ предмет"], ["words", "Только слова"], ["items", "Только предметы"], ["and", "Слово И предмет"]];

export default function App() {
  const watch = useWatch();
  const [tab, setTab] = useState("Поиск");
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
        <span className={`btn status${watch.watching ? " on" : ""}`}>{watch.watching ? "✓ Слежу" : "Не слежу"}</span>
        <label className="keywords">
          <span className="muted">Ключевые слова</span>
          <input className="field" value={watch.keywords} onChange={(e) => watch.setKeywords(e.target.value)}
            aria-label="Ключевые слова" />
        </label>
        <select className="field mode" value={watch.mode} onChange={(e) => watch.setMode(e.target.value)} aria-label="Режим поиска">
          {MODES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <button className="btn" title="Свернуть в полосу поверх игры (позже)">В накладку</button>
        <button className="btn">Настройки</button>
      </div>

      <nav className="tabs" role="tablist">
        {TABS.map((name) => (
          <button key={name} role="tab" aria-selected={tab === name} className={`tab${tab === name ? " on" : ""}`}
            onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {tab === "Поиск" ? (
        <main className="search">
          <section className="card feed-card"><Feed entries={watch.entries} alerts={{ state: watch.state, remaining: watch.remaining, onAccept: watch.accept }} /></section>
          <ItemsPanel checked={watch.checked} onChange={watch.setChecked} />
        </main>
      ) : (
        <main className="soon"><p>Вкладка «{tab}» будет следующей.</p></main>
      )}
      <Toasts toasts={watch.toasts} remaining={watch.remaining} onAccept={watch.acceptToast}
        onSnooze={watch.snoozeToast} onDismiss={watch.dismissToast} />
    </div>
  );
}
