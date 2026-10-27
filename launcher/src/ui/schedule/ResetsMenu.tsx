import { useEffect, useRef, useState } from "react";

import { daysText, Reset, ResetDraft } from "../../core/schedule/resets";
import { DAYS } from "../../core/schedule/reminders";
import { IconBell, IconClose, IconPencil, IconPlus, IconReset } from "../icons";
import { announce, useYields } from "./popover";
import type { Schedule } from "./useSchedule";

const SHORT: Record<string, string> = { mon: "Пн", tue: "Вт", wed: "Ср", thu: "Чт", fri: "Пт", sat: "Сб", sun: "Вс" };

/**
 * The «+ Откат» button of the schedule bar and its menu. Each reset is one line: bell, name, days and time, and on the
 * right «изменить» and «удалить». «Изменить» opens the line as a small form (name, days, time); «Свой откат» opens the
 * same form empty. A server reset that is deleted is only hidden (a link brings it back), and any deletion can be undone
 * for 30 s.
 */
export function ResetsMenu({ schedule }: { schedule: Schedule }) {
  const { resets, resetBells } = schedule;
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<string | null>(null); // the id of the reset in the form, "new" for a new one
  const root = useRef<HTMLDivElement>(null);
  const all = resets.length > 0 && resets.every((r) => resetBells.has(r.id));
  useYields("resets", () => setOpen(false));

  useEffect(() => {
    if (!open) { setEditing(null); return; }
    const outside = (e: Event) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopPropagation();
      setEditing((now) => { if (now === null) setOpen(false); return null; }); // Esc closes the form first, then the menu
    };
    window.addEventListener("pointerdown", outside);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("pointerdown", outside); window.removeEventListener("keydown", esc); };
  }, [open]);

  return (
    <div className="sch-links" ref={root}>
      <button className={`btn rs-add${open ? " on" : ""}`} aria-haspopup="dialog" aria-expanded={open}
        title="Откаты: время, дни, свои откаты" aria-label="Откат: добавить или изменить"
        onClick={() => { if (!open) announce("resets"); setOpen(!open); }}>
        <IconReset />+ Откат
      </button>
      {open && (
        <div className="sch-linkmenu sch-resetmenu" role="dialog" aria-label="Откаты">
          <div className="rs-head">
            <h3>Откаты</h3>
            <button className={`btn${all ? " primary" : ""}`} aria-pressed={all} onClick={schedule.toggleAllResets}
              title={all ? "Выключить напоминания обо всех откатах" : "Включить напоминания обо всех откатах"}>
              <IconBell on={all} />{all ? "Напоминаю обо всех" : "Напоминать обо всех"}
            </button>
          </div>

          <ul className="rows">
            {resets.map((r) => editing === r.id
              ? <li key={r.id} className="editing"><ResetForm initial={r} schedule={schedule} reset={r} onDone={() => setEditing(null)} /></li>
              : <ResetLine key={r.id} reset={r} schedule={schedule} onEdit={() => setEditing(r.id)} />)}
            {resets.length === 0 && <li className="empty">Откатов нет. Добавь свой ниже.</li>}
          </ul>

          {schedule.resetUndo && (
            <div className="undo" role="status">
              <span>{schedule.resetUndo.label}</span>
              <button className="btn sm" onClick={schedule.undoReset}>Отменить</button>
            </div>
          )}

          {editing === "new"
            ? <div className="editing"><ResetForm initial={{ name: "", days: [...DAYS], time: "09:00" }} schedule={schedule} reset={null} onDone={() => setEditing(null)} /></div>
            : <button className="btn add" onClick={() => setEditing("new")}><IconPlus />Свой откат</button>}

          <p className="hint">
            Время по МСК, как на сервере.
            {schedule.hiddenResets > 0 && <> Скрыто откатов сервера: {schedule.hiddenResets}. <button className="link accent" onClick={schedule.restoreResets}>Вернуть</button></>}
          </p>
        </div>
      )}
    </div>
  );
}

function ResetLine({ reset, schedule, onEdit }: { reset: Reset; schedule: Schedule; onEdit(): void }) {
  const bell = schedule.resetBells.has(reset.id);
  return (
    <li className={bell ? "belled" : ""}>
      <button className={`btn sq bell${bell ? " on" : ""}`} aria-pressed={bell} title={bell ? "Не напоминать" : "Напоминать"}
        aria-label={`${bell ? "Не напоминать" : "Напоминать"}: ${reset.name}`} onClick={() => schedule.toggleResetBell(reset)}><IconBell on={bell} /></button>
      <button className="rs-what" onClick={onEdit} title="Изменить">
        <b>{reset.name}</b>
        <span>{daysText(reset.days)} · {reset.time}{reset.own ? " · свой" : reset.edited ? " · изменён" : ""}</span>
      </button>
      <button className="btn sq ghost" title="Изменить" aria-label={`Изменить: ${reset.name}`} onClick={onEdit}><IconPencil /></button>
      <button className="btn sq ghost red" title={reset.own ? "Удалить" : "Скрыть откат сервера"} aria-label={`Удалить: ${reset.name}`}
        onClick={() => schedule.removeReset(reset)}><IconClose /></button>
    </li>
  );
}

/** The form of one reset: name, days (with «Каждый день»), time. */
function ResetForm({ initial, reset, schedule, onDone }: { initial: ResetDraft; reset: Reset | null; schedule: Schedule; onDone(): void }) {
  const [draft, setDraft] = useState<ResetDraft>({ ...initial, days: [...initial.days] });
  const [error, setError] = useState("");
  const name = useRef<HTMLInputElement>(null);
  useEffect(() => { name.current?.focus(); }, []);
  const every = draft.days.length === 7;
  const flip = (d: string) => setDraft({ ...draft, days: draft.days.includes(d) ? draft.days.filter((x) => x !== d) : [...draft.days, d] });
  const save = () => {
    const message = schedule.saveReset(reset, draft);
    setError(message ?? "");
    if (!message) onDone();
  };
  return (
    <div className="rs-form" onKeyDown={(e) => { if (e.key === "Enter" && (e.target as HTMLElement).tagName === "INPUT") { e.preventDefault(); save(); } }}>
      <input ref={name} className="inp" value={draft.name} placeholder="Название отката" maxLength={40} aria-label="Название отката"
        onChange={(e) => { setDraft({ ...draft, name: e.target.value }); setError(""); }} />
      <div className="rs-days" role="group" aria-label="Дни">
        <button className={every ? "on" : ""} aria-pressed={every} onClick={() => setDraft({ ...draft, days: every ? [] : [...DAYS] })}>Каждый день</button>
        {DAYS.map((d) => <button key={d} className={draft.days.includes(d) ? "on" : ""} aria-pressed={draft.days.includes(d)} onClick={() => flip(d)}>{SHORT[d]}</button>)}
      </div>
      <div className="ctl-row">
        <input className="inp t" type="time" aria-label="Время по МСК" value={draft.time} onChange={(e) => { setDraft({ ...draft, time: e.target.value }); setError(""); }} />
        <span className="muted">МСК</span>
        <span className="spacer" />
        <button className="btn" onClick={onDone}>Отмена</button>
        <button className="btn primary" onClick={save}>{reset ? "Сохранить" : "Добавить"}</button>
      </div>
      {error && <div className="err" role="alert">{error}</div>}
    </div>
  );
}
