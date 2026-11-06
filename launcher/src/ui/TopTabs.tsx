// The top tabs (core/tabs.ts): plain tabs and two menu tabs, «Калькуляторы» and «База данных», split into groups by
// thin lines. A menu tab opens its list under it; the orange line stands under the tab whose screen is shown, a menu
// tab included (it then also names the open section). Mouse and keyboard: arrows move in the list, Enter or a click
// opens, Esc and a click outside close; one floating layer at a time (schedule/popover).
import { Fragment, useCallback, useEffect, useId, useRef, useState } from "react";

import { sectionCounts } from "../core/db/sections";
import { LIVE_TABS, TOP, menuOf, tabLabel, type TopTab } from "../core/tabs";
import { pulseDb } from "./db/pulseDb";
import { Glide } from "./fx";
import { IconCheck, IconChevron } from "./icons";
import { Presence } from "./motion";
import { announce, useYields } from "./schedule/popover";

interface Props { tab: string; onPick(id: string): void }

export function TopTabs({ tab, onPick }: Props) {
  return (
    <nav className="tabs" role="tablist">
      {TOP.map((group, i) => (
        <Fragment key={i}>
          {i > 0 && <span className="tabs-sep" aria-hidden="true" />}
          {group.map((item) => item.menu
            ? <MenuTab key={item.id} item={item} tab={tab} onPick={onPick} />
            : <button key={item.id} role="tab" aria-selected={tab === item.id} className={`tab${tab === item.id ? " on" : ""}`}
                onClick={() => onPick(item.id)}>{item.label}{tab === item.id && <Glide group="tab-line" className="tab-line" />}</button>)}
        </Fragment>
      ))}
    </nav>
  );
}

let counted: Promise<Record<string, number>> | null = null;
/** The database sections' sizes, read once from pulse.db (none when there is no database). */
function counts(): Promise<Record<string, number>> {
  counted ??= pulseDb().then((all) => (all ? sectionCounts(all) : {})).catch(() => ({}));
  return counted;
}

function MenuTab({ item, tab, onPick }: { item: TopTab; tab: string; onPick(id: string): void }) {
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const [sizes, setSizes] = useState<Record<string, number>>({});
  const root = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const list = useId();
  const entries = item.menu!.flatMap((g) => g.items);
  const here = menuOf(tab) === item.label; // a screen of this menu is shown
  const close = useCallback(() => setOpen(false), []);
  useYields(`tabs-${item.id}`, close);

  const show = () => {
    announce(`tabs-${item.id}`);
    setCursor(Math.max(0, entries.findIndex((s) => s.id === tab)));
    setOpen(true);
    if (item.id === "db") counts().then(setSizes);
  };
  const choose = (id: string) => { onPick(id); setOpen(false); button.current?.focus(); };

  useEffect(() => {
    if (!open) return;
    const outside = (e: Event) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    window.addEventListener("pointerdown", outside);
    return () => window.removeEventListener("pointerdown", outside);
  }, [open]);

  const keys = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); show(); }
      return;
    }
    const n = entries.length;
    if (e.key === "Escape") { e.stopPropagation(); setOpen(false); button.current?.focus(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => (c + 1) % n); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => (c + n - 1) % n); }
    else if (e.key === "Home") { e.preventDefault(); setCursor(0); }
    else if (e.key === "End") { e.preventDefault(); setCursor(n - 1); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(entries[cursor].id); }
    else if (e.key === "Tab") setOpen(false);
  };

  const note = (id: string) => {
    if (sizes[id] !== undefined) return sizes[id].toLocaleString("ru-RU");
    return LIVE_TABS.includes(id) ? "" : item.id === "db" && Object.keys(sizes).length === 0 ? "" : "скоро";
  };

  return (
    <span className="tab-host" ref={root} onKeyDown={keys}>
      <button ref={button} role="tab" aria-selected={here} aria-haspopup="menu" aria-expanded={open}
        aria-controls={open ? list : undefined} aria-activedescendant={open ? `${list}-${cursor}` : undefined}
        className={`tab menu-tab${here ? " on" : ""}${open ? " open" : ""}`} onClick={() => (open ? setOpen(false) : show())}>
        {item.label}{here && <span className="tab-sub">{tabLabel(tab)}</span>}
        <span className={`tab-chev${open ? " open" : ""}`} aria-hidden="true"><IconChevron open={false} /></span>
        {here && <Glide group="tab-line" className="tab-line" />}
      </button>
      <Presence show={open}>
        <div id={list} className="tab-menu" role="menu" aria-label={item.label}>
          {item.menu!.map((group) => (
            <div key={group.title || item.id} className="tab-menu-grp" role="group" aria-label={group.title || item.label}>
              {group.title && <div className="tab-menu-title">{group.title}</div>}
              {group.items.map((s) => {
                const i = entries.indexOf(s);
                const text = note(s.id);
                return (
                  <button key={s.id} id={`${list}-${i}`} role="menuitem" tabIndex={-1}
                    className={`tab-menu-item${s.id === tab ? " on" : ""}${i === cursor ? " cur" : ""}`}
                    onPointerEnter={() => setCursor(i)} onClick={() => choose(s.id)}>
                    <span>{s.label}</span>
                    {s.id === tab ? <IconCheck /> : <em className={text === "скоро" ? "later" : ""}>{text}</em>}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </Presence>
    </span>
  );
}
