// The schedule's sets in the bar, beside «Фильтры» (docs/concepts/schedule/presets-plus.html): an orange chip with the
// active set, and its dropdown. A row switches the whole schedule (own events, reminders, filters, resets); ✎ renames,
// × and «Удалить?» delete; «+» in the head adds a copy of the schedule now (up to four); «Очистить всё» (asked twice)
// empties the active set (server and own events, resets, reminders), with 10 s to take it back.
import { useEffect, useRef, useState } from "react";

import { MAX_PRESETS } from "../../core/schedule/presets";
import { IconCheck, IconClose, IconPencil, IconPlus } from "../icons";
import { Presence } from "../motion";
import { announce, useYields } from "./popover";
import type { Schedule } from "./useSchedule";

const ASK_MS = 5000;

const ownText = (n: number) => {
  const tail = n % 10 === 1 && n % 100 !== 11 ? "своё" : "своих";
  return n ? `${n} ${tail}` : "без своих";
};

export function PresetMenu({ schedule }: { schedule: Schedule }) {
  const { presets, active } = schedule.presets;
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [asking, setAsking] = useState<number | null>(null);
  const [clearing, setClearing] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useYields("presets", () => setOpen(false));

  useEffect(() => {
    if (!open) { setEditing(null); setAsking(null); setClearing(false); return; }
    const outside = (e: Event) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopPropagation();
      setEditing((now) => { if (now === null) setOpen(false); return null; }); // Esc leaves the name first, then the menu
    };
    window.addEventListener("pointerdown", outside);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("pointerdown", outside); window.removeEventListener("keydown", esc); };
  }, [open]);
  useEffect(() => { if (editing !== null) input.current?.select(); }, [editing]);
  useEffect(() => { // «Удалить?» and «Точно очистить?» go back by themselves
    if (asking === null && !clearing) return;
    const t = setTimeout(() => { setAsking(null); setClearing(false); }, ASK_MS);
    return () => clearTimeout(t);
  }, [asking, clearing]);

  const finish = (index: number, text: string | null) => {
    if (text !== null) schedule.renamePreset(index, text);
    setEditing(null);
  };

  return (
    <div className="sch-presets" ref={root}>
      <button className={`sch-chip sch-preset-chip${open ? " open" : ""}`} aria-haspopup="listbox" aria-expanded={open}
        title="Наборы расписания: свои события, напоминания, фильтры и откаты"
        onClick={() => { if (!open) announce("presets"); setOpen(!open); }}>
        <i className="dot" /><b>{presets[active]?.title}</b><em>{active + 1} из {presets.length}</em>
        <svg className="caret" width="10" height="10" viewBox="0 0 10 10" aria-hidden><path d="M2 3.5 5 6.5 8 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
      </button>
      <Presence show={open}>
        <div className="sch-preset-drop" role="dialog" aria-label="Наборы расписания">
          <div className="hd">
            <span>Наборы расписания <em>· до {MAX_PRESETS}</em></span>
            <button className="add" disabled={presets.length >= MAX_PRESETS} title="Новый набор: копия текущего расписания"
              aria-label="Новый набор" onClick={schedule.addPreset}><IconPlus /></button>
          </div>
          <ul role="listbox" aria-label="Наборы">
            {presets.map((p, i) => (
              <li key={i} role="option" aria-selected={i === active} className={i === active ? "on" : ""}
                onClick={() => { if (editing !== i) schedule.selectPreset(i); }}>
                <span className="mark">{i === active && <IconCheck />}</span>
                {editing === i
                  ? <input ref={input} defaultValue={p.title} maxLength={24} aria-label="Название набора" onClick={(e) => e.stopPropagation()}
                    onBlur={(e) => finish(i, e.currentTarget.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") finish(i, e.currentTarget.value); }} />
                  : <><span className="name">{p.title}</span><span className="meta">{ownText(schedule.presetOwn[i] ?? 0)}</span></>}
                {editing !== i && <button className="act" title="Переименовать" aria-label={`Переименовать ${p.title}`}
                  onClick={(e) => { e.stopPropagation(); setEditing(i); }}><IconPencil /></button>}
                {presets.length > 1 && editing !== i && (asking === i
                  ? <button className="act ask" onClick={(e) => { e.stopPropagation(); setAsking(null); schedule.removePreset(i); }}>Удалить?</button>
                  : <button className="act del" title="Удалить" aria-label={`Удалить ${p.title}`}
                    onClick={(e) => { e.stopPropagation(); setAsking(i); }}><IconClose /></button>)}
              </li>
            ))}
          </ul>
          <div className="sep" />
          <button className={`clear${clearing ? " ask" : ""}`}
            onClick={() => { if (!clearing) { setClearing(true); return; } setClearing(false); schedule.clearPreset(); }}>
            {clearing ? "Точно очистить всё?" : "Очистить всё"}
          </button>
          <p className="hint">Убирает из набора всё: события сервера и свои, откаты, напоминания. Сетка становится пустой. 10 секунд можно отменить.</p>
        </div>
      </Presence>
    </div>
  );
}
