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
  const find = (text: string) => { setQuery(text); browser.search(text); redraw(); };
  const refilter = (filter = browser.filter) => { browser.setFilter(filter); browser.search(query); redraw(); };
  // while searching, the list keeps only the items whose name holds every word (or the level), all groups open
  const found = new Set(browser.matches);
  const groups = [...browser.shown]
    .map(([category, list]) => [category, searching ? list.filter((item) => found.has(item.id)) : list] as [string, WatchItem[]])
    .filter(([, list]) => list.length);
  const limit = searching ? SHOWN_FOUND : SHOWN_PER_GROUP;
  const open = (category: string) => searching || !browser.collapsed.includes(category);
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
            <div className="group-head" onClick={() => { if (!searching) { browser.toggleCollapsed(category); redraw(); } }} role="button" tabIndex={0}
              aria-expanded={open(category)}
              onKeyDown={(e) => { if (!searching && (e.key === "Enter" || e.key === " ")) { browser.toggleCollapsed(category); redraw(); } }}>
              <IconChevron open={open(category)} />
              <b>{category}</b>
              <span className="muted">· {list.length} · отмечено {list.filter((i) => browser.checked.has(i.id)).length}</span>
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
                <span className={`name g-${item.grade}`}>{item.name}</span>
                <span className="lvl">{item.level}</span>
              </label>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}
