// A themed one-choice menu for the bestiary's filters and sort: a pill button that opens a list of options under it.
// Mouse and keyboard: the arrows move, Enter or a click chooses, Esc and a click outside close; one floating layer at a time.
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

import { IconCheck, IconChevron } from "../icons";
import { Presence } from "../motion";
import { announce, useYields } from "../schedule/popover";

export interface PickMenuProps {
  /** Unique on the screen: opening one menu closes the others. */
  id: string;
  /** What the button says (the current choice, or the name of the filter). */
  text: string;
  icon?: ReactNode;
  /** The filter is on: the button is lit in the accent colour. */
  lit?: boolean;
  options: [label: string, value: string][];
  value: string;
  onPick(value: string): void;
  /** The list opens under the button's right edge instead of the left one. */
  right?: boolean;
  label: string;
  /** A class for an option's text by its value (a grade's colour). */
  tone?(value: string): string;
}

export function PickMenu({ id, text, icon, lit, options, value, onPick, right, label, tone }: PickMenuProps) {
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const list = useId();
  const close = useCallback(() => setOpen(false), []);
  useYields(`bst-${id}`, close);

  const show = () => {
    announce(`bst-${id}`);
    setCursor(Math.max(0, options.findIndex(([, v]) => v === value)));
    setOpen(true);
  };
  const choose = (v: string) => { onPick(v); setOpen(false); button.current?.focus(); };

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
    if (e.key === "Escape") { e.stopPropagation(); setOpen(false); button.current?.focus(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => (c + 1) % options.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => (c + options.length - 1) % options.length); }
    else if (e.key === "Home") { e.preventDefault(); setCursor(0); }
    else if (e.key === "End") { e.preventDefault(); setCursor(options.length - 1); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(options[cursor][1]); }
    else if (e.key === "Tab") setOpen(false);
  };

  return (
    <div className="bst-menu" ref={root} onKeyDown={keys}>
      <button ref={button} type="button" className={`bst-flt${lit ? " lit" : ""}${open ? " open" : ""}`} aria-haspopup="listbox" aria-expanded={open}
        aria-controls={open ? list : undefined} aria-activedescendant={open ? `${list}-${cursor}` : undefined} aria-label={`${label}: ${text}`} onClick={() => (open ? setOpen(false) : show())}>
        {icon}<span>{text}</span><span className={`bst-flt-chev${open ? " open" : ""}`}><IconChevron open={false} /></span>
      </button>
      <Presence show={open}>
        <ul id={list} className={`bst-pop${right ? " right" : ""}`} role="listbox" aria-label={label}>
          {options.map(([name, v], i) => (
            <li key={v} id={`${list}-${i}`} role="option" aria-selected={v === value} className={`${v === value ? "on" : ""}${i === cursor ? " cur" : ""}`}
              onPointerEnter={() => setCursor(i)} onClick={() => choose(v)}>
              <span className={tone?.(v) || undefined}>{name}</span>{v === value && <IconCheck />}
            </li>
          ))}
        </ul>
      </Presence>
    </div>
  );
}
