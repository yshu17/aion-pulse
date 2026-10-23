import { useMemo, useReducer, useState } from "react";

import { GRADE_LABELS, ItemBrowser } from "../core/items/browser";
import type { WatchItem } from "../core/items/catalog";
import { watchItems } from "./data";
import { Icon } from "./Icon";
import { IconChevron, IconClose } from "./icons";

const SHOWN_PER_GROUP = 80;
const SHOWN_FOUND = 120; // per group while searching: hundreds of rows with pictures slow the panel down

export function ItemsPanel({ checked, onChange }: { checked: Set<string>; onChange(ids: Set<string>): void }) {
  const browser = useMemo(() => new ItemBrowser(watchItems, checked, []), []); // eslint-disable-line react-hooks/exhaustive-deps
  const [, redraw] = useReducer((n: number) => n + 1, 0);
  const [query, setQuery] = useState("");
  const commit = () => { onChange(new Set(browser.checked)); redraw(); };
  const searching = query.trim() !== "";
  const find = (text: string) => { setQuery(text); setSearchFolded(new Set()); browser.search(text); redraw(); };
  const refilter = (filter = browser.filter) => { browser.setFilter(filter); browser.search(query); redraw(); };
  // while searching, the list keeps only the items whose name holds every word (or the level), all groups open
  const found = new Set(browser.matches);
  const groups = [...browser.shown]
    .map(([category, list]) => [category, searching ? list.filter((item) => found.has(item.id)) : list] as [string, WatchItem[]])
    .filter(([, list]) => list.length);
  const limit = searching ? SHOWN_FOUND : SHOWN_PER_GROUP;
  // groups fold while searching too; that folding is the search's own and does not touch the saved one
  const [searchFolded, setSearchFolded] = useState<Set<string>>(new Set());
  const open = (category: string) => (searching ? !searchFolded.has(category) : !browser.collapsed.includes(category));
  const fold = (category: string) => {
    if (!searching) { browser.toggleCollapsed(category); redraw(); return; }
    const next = new Set(searchFolded);
    if (next.has(category)) next.delete(category); else next.add(category);
    setSearchFolded(next);
  };
  /** «все» of a group: while searching, only the items that are shown. */
  const allChecked = (category: string, list: WatchItem[]) =>
    searching ? list.every((item) => browser.checked.has(item.id)) : browser.groupChecked(category);
  const checkAll = (category: string, list: WatchItem[]) => {
    const value = !allChecked(category, list);
    if (!searching) browser.setGroup(category, value);
    else for (const item of list) if (browser.checked.has(item.id) !== value) browser.toggleItem(item.id);
    commit();
  };

  return (
    <section className="card items" aria-label="Что искать">
      <header className="card-head">
        <h2>Что искать</h2>
        <span className="spacer" />
        <button className="btn" onClick={() => { browser.setAll(true); commit(); }}>Все</button>
        <button className="btn" onClick={() => { browser.setAll(false); commit(); }}>Снять</button>
      </header>
      <div className="search-field">
        <input className="field" placeholder="Найти предмет: название или уровень" value={query} aria-label="Найти предмет"
          onChange={(e) => find(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") find(""); }} />
        {searching && <button className="x" aria-label="Очистить поиск" onClick={() => find("")}><IconClose /></button>}
      </div>
      {searching && <div className="muted found-count" aria-live="polite">
        {found.size ? `Найдено: ${found.size}` : "Ничего не найдено — проверь слово или сними фильтры редкости и типа"}</div>}
      <div className="chips">
        {browser.grades.map((grade) => (
          <button key={grade} className={`chip g-${grade} ${browser.chipState(grade)}`}
            onClick={() => refilter(browser.toggleGrade(grade))}>{GRADE_LABELS[grade] ?? grade}</button>
        ))}
      </div>
      <select className="field" aria-label="Тип" value={browser.filter.type || "Все типы"}
        onChange={(e) => refilter(browser.withLevelsType(browser.filter.level_min, browser.filter.level_max, e.target.value))}>
        {browser.typeChoices().map((choice) => <option key={choice}>{choice}</option>)}
      </select>
      <div className="groups">
        {groups.map(([category, list]) => (
          <div key={category} className="group">
            <div className="group-head" onClick={() => fold(category)} role="button" tabIndex={0} aria-expanded={open(category)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fold(category); } }}>
              <IconChevron open={open(category)} />
              <b className="group-name">{category}</b>
              <span className="muted count">{searching ? `найдено ${list.length}` : `${list.filter((i) => browser.checked.has(i.id)).length} из ${list.length}`}</span>
              <span className="spacer" />
              <label className="check" onClick={(e) => e.stopPropagation()}>
                <input type="checkbox" checked={allChecked(category, list)} onChange={() => checkAll(category, list)} />
                <span className="box" /><span className="muted">все</span>
              </label>
            </div>
            {open(category) && list.length > limit && (
              <div className="muted more">Показаны {limit} из {list.length} — {searching ? "уточни поиск" : "найди предмет поиском"}</div>)}
            {open(category) && list.slice(0, limit).map((item: WatchItem) => (
              <label key={item.id} id={`item-${item.id}`} className="item">
                <span className="check">
                  <input type="checkbox" checked={browser.checked.has(item.id)}
                    onChange={() => { browser.toggleItem(item.id); commit(); }} />
                  <span className="box" />
                </span>
                <Icon name={item.icon} />
                <span className={`name g-${item.grade}`}><Marked text={item.name} query={query} /></span>
                <span className="lvl">{item.level}</span>
              </label>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

/** The name with the searched words marked. */
function Marked({ text, query }: { text: string; query: string }) {
  const words = query.trim().toLowerCase().replace(/ё/g, "е").split(/\s+/).filter((w) => w && !/^\d+$/.test(w));
  if (!words.length) return <>{text}</>;
  const norm = text.toLowerCase().replace(/ё/g, "е");
  const marks: boolean[] = new Array(text.length).fill(false);
  for (const w of words) for (let i = norm.indexOf(w); i >= 0; i = norm.indexOf(w, i + 1)) marks.fill(true, i, i + w.length);
  const parts: [string, boolean][] = [];
  for (let i = 0; i < text.length; i++) {
    if (parts.length && parts[parts.length - 1][1] === marks[i]) parts[parts.length - 1][0] += text[i];
    else parts.push([text[i], marks[i]]);
  }
  return <>{parts.map(([part, on], i) => (on ? <mark key={i}>{part}</mark> : <span key={i}>{part}</span>))}</>;
}
