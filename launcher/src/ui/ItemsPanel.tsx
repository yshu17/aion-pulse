import { useMemo, useReducer, useState } from "react";

import { GRADE_LABELS, ItemBrowser } from "../core/items/browser";
import type { WatchItem } from "../core/items/catalog";
import { watchItems } from "./data";
import { Icon } from "./Icon";

const SHOWN_PER_GROUP = 80;

export function ItemsPanel({ checked, onChange }: { checked: Set<string>; onChange(ids: Set<string>): void }) {
  const browser = useMemo(() => new ItemBrowser(watchItems, checked, []), []); // eslint-disable-line react-hooks/exhaustive-deps
  const [, redraw] = useReducer((n: number) => n + 1, 0);
  const [query, setQuery] = useState("");
  const commit = () => { onChange(new Set(browser.checked)); redraw(); };
  const refilter = (filter = browser.filter) => { browser.setFilter(filter); redraw(); };
  const open = (category: string) => !browser.collapsed.includes(category);

  return (
    <section className="card items" aria-label="Что искать">
      <header className="card-head">
        <h2>Что искать</h2>
        <span className="spacer" />
        <button className="btn" onClick={() => { browser.setAll(true); commit(); }}>Все</button>
        <button className="btn" onClick={() => { browser.setAll(false); commit(); }}>Снять</button>
      </header>
      <input className="field" placeholder="Найти предмет" value={query} aria-label="Найти предмет"
        onChange={(e) => { setQuery(e.target.value); browser.search(e.target.value); redraw(); }}
        onKeyDown={(e) => {
          if (e.key !== "Enter") return;
          const id = browser.step(e.shiftKey ? -1 : 1);
          redraw();
          if (id) requestAnimationFrame(() => document.getElementById(`item-${id}`)?.scrollIntoView({ block: "center" }));
        }} />
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
        {[...browser.shown].map(([category, list]) => (
          <div key={category} className="group">
            <div className="group-head" onClick={() => { browser.toggleCollapsed(category); redraw(); }} role="button" tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { browser.toggleCollapsed(category); redraw(); } }}>
              <span className={`caret${open(category) ? " open" : ""}`}>›</span>
              <b>{category}</b>
              <span className="muted">· {list.length} · отмечено {list.filter((i) => browser.checked.has(i.id)).length}</span>
              <span className="spacer" />
              <label className="check" onClick={(e) => e.stopPropagation()}>
                <input type="checkbox" checked={browser.groupChecked(category)}
                  onChange={() => { browser.setGroup(category, !browser.groupChecked(category)); commit(); }} />
                <span className="box" /><span className="muted">все</span>
              </label>
            </div>
            {open(category) && list.slice(0, SHOWN_PER_GROUP).map((item: WatchItem) => (
              <label key={item.id} id={`item-${item.id}`} className={`item${browser.matches.includes(item.id) ? " found" : ""}`}>
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
