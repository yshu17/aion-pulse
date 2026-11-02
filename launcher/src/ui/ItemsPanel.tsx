import { Dispatch, memo, SetStateAction, useCallback, useDeferredValue, useMemo, useReducer, useRef, useState } from "react";

import { itemLink } from "../core/chat/parser";
import { GRADE_LABELS, ItemBrowser } from "../core/items/browser";
import type { WatchItem } from "../core/items/catalog";
import { watchItems } from "./data";
import { Icon } from "./Icon";
import { IconCheck, IconChevron, IconClose, IconCopy, IconEye } from "./icons";
import { useOpenItem } from "./ItemCard";

const SHOWN_PER_GROUP = 80;
const OPEN_AT_START = "Рудра и Фланас"; // the other groups start folded: the list is long
const SHOWN_FOUND = 120; // per group while searching: hundreds of rows with pictures slow the panel down

export function ItemsPanel({ checked, onChange }: { checked: Set<string>; onChange(ids: Set<string>): void }) {
  const browser = useMemo(() => {
    const list = new ItemBrowser(watchItems, checked, []);
    for (const category of list.groups.keys()) if (category !== OPEN_AT_START) list.toggleCollapsed(category);
    return list;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const openItem = useOpenItem();
  const openRef = useRef(openItem); // the list gets stable callbacks: it must not redraw on every keystroke
  openRef.current = openItem;
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const [copiedId, setCopiedId] = useState<string | null>(null);
  // the item as a link of the game's chat: «[item:166000103]» pasted in the game is the item's own link; a tick shows it went there
  const copyId = useCallback((id: string) => {
    navigator.clipboard?.writeText(itemLink(id)).then(() => {
      setCopiedId(id);
      window.setTimeout(() => setCopiedId((now) => (now === id ? null : now)), 1200);
    }).catch(() => {});
  }, []);
  const peek = useCallback((id: string, x: number, y: number) => openRef.current({ id, x, y }), []);
  const [version, redraw] = useReducer((n: number) => n + 1, 0);
  const [query, setQuery] = useState("");
  // the list follows the search a moment later: typing renders only the input, the list is drawn in a low-priority pass
  const deferred = useDeferredValue(query);
  const commit = useCallback(() => { onChangeRef.current(new Set(browser.checked)); redraw(); }, [browser]);
  const [searchFolded, setSearchFolded] = useState<Set<string>>(new Set());
  const find = (text: string) => {
    setQuery(text);
    if (searchFolded.size) setSearchFolded(new Set());
  };
  const refilter = (filter = browser.filter) => { browser.setFilter(filter); redraw(); };
  const typing = query.trim() !== "";

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
        {typing && <button className="x" aria-label="Очистить поиск" onClick={() => find("")}><IconClose /></button>}
      </div>
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
      <ItemsList browser={browser} version={version} query={deferred} searchFolded={searchFolded} setSearchFolded={setSearchFolded}
        redraw={redraw} commit={commit} copiedId={copiedId} copyId={copyId} peek={peek} />
    </section>
  );
}

interface ListProps {
  browser: ItemBrowser;
  version: number; // changes with every redraw of the browser's own state (checks, folds, filters)
  query: string; // the deferred search text: the list follows it a moment after the input
  searchFolded: Set<string>;
  setSearchFolded: Dispatch<SetStateAction<Set<string>>>;
  redraw: () => void;
  commit: () => void;
  copiedId: string | null;
  copyId(id: string): void;
  peek(id: string, x: number, y: number): void;
}

/** The found line and the groups with their rows. Memoized: a keystroke in the input does not draw it again. */
const ItemsList = memo(function ItemsList({ browser, version, query, searchFolded, setSearchFolded, redraw, commit, copiedId, copyId, peek }: ListProps) {
  const searching = query.trim() !== "";
  const found = useMemo(() => {
    browser.search(query);
    return new Set(browser.matches);
  }, [browser, query, version]);
  // the checked items go to one group at the top; the groups below keep only the items not checked
  const base = [...browser.shown]
    .map(([category, list]) => [category, searching ? list.filter((item) => found.has(item.id)) : list] as [string, WatchItem[]])
    .filter(([, list]) => list.length);
  const picked = base.flatMap(([, list]) => list.filter((item) => browser.checked.has(item.id)));
  const groups = base
    .map(([category, list]) => [category, list.filter((item) => !browser.checked.has(item.id))] as [string, WatchItem[]])
    .filter(([, list]) => list.length);
  const limit = searching ? SHOWN_FOUND : SHOWN_PER_GROUP;
  // groups fold while searching too; that folding is the search's own and does not touch the saved one
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
  const row = (item: WatchItem) => (
    <label key={item.id} id={`item-${item.id}`} className="item">
      <span className="check">
        <input type="checkbox" checked={browser.checked.has(item.id)}
          onChange={() => { browser.toggleItem(item.id); commit(); }} />
        <span className="box" />
      </span>
      <Icon name={item.icon} />
      <span className={`name g-${item.grade}`}><Marked text={item.name} query={query} /></span>
      <span className="lvl">{item.level}</span>
      <button type="button" className="peek" aria-label={`Описание: ${item.name}`} title="Открыть описание"
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); peek(item.id, e.clientX, e.clientY); }}>
        <IconEye />
      </button>
      <button type="button" className={`peek copy-id${copiedId === item.id ? " done" : ""}`} aria-label={`Копировать ссылку на предмет: ${item.name}`}
        title={`Копировать ссылку для чата игры: ${itemLink(item.id)}`}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); copyId(item.id); }}>
        {copiedId === item.id ? <IconCheck /> : <IconCopy />}
      </button>
    </label>
  );

  return (
    <>
      {searching && <div className="muted found-count" aria-live="polite">
        {found.size ? `Найдено: ${found.size}` : "Ничего не найдено — проверь слово или сними фильтры редкости и типа"}</div>}
      <div className="groups">
        {picked.length > 0 && (
          <div className="group picked">
            <div className="group-head static">
              <b className="group-name">Выбрано</b>
              <span className="muted count">{picked.length}</span>
              <span className="spacer" />
              <label className="check">
                <input type="checkbox" checked onChange={() => { for (const item of picked) browser.toggleItem(item.id); commit(); }} />
                <span className="box" /><span className="muted">все</span>
              </label>
            </div>
            {picked.length > limit && <div className="muted more">Показаны {limit} из {picked.length}</div>}
            {picked.slice(0, limit).map(row)}
          </div>
        )}
        {groups.map(([category, list]) => (
          <div key={category} className="group">
            <div className="group-head" onClick={() => fold(category)} role="button" tabIndex={0} aria-expanded={open(category)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fold(category); } }}>
              <IconChevron open={open(category)} />
              <b className="group-name">{category}</b>
              <span className="muted count">{searching ? `найдено ${list.length}` : `${list.length}`}</span>
              <span className="spacer" />
              <label className="check" onClick={(e) => e.stopPropagation()}>
                <input type="checkbox" checked={allChecked(category, list)} onChange={() => checkAll(category, list)} />
                <span className="box" /><span className="muted">все</span>
              </label>
            </div>
            {open(category) && list.length > limit && (
              <div className="muted more">Показаны {limit} из {list.length} — {searching ? "уточни поиск" : "найди предмет поиском"}</div>)}
            {open(category) && list.slice(0, limit).map(row)}
          </div>
        ))}
      </div>
    </>
  );
});

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
