import { useEffect, useRef, useState } from "react";

import { Reset } from "../../core/schedule/resets";
import { DAY_NAMES } from "../../core/schedule/timing";
import { DAYS } from "../../core/schedule/reminders";
import scheduleText from "../../../../data/schedule.json?raw";
import { IconBell, IconClose, IconPlus, IconReset } from "../icons";
import type { Schedule } from "./useSchedule";

const WEEKLY = "weekly";

/**
 * The «Откаты» button of the schedule bar and its menu: the daily and weekly resets with their time (server time) that
 * can be changed, a bell on each and one for the whole block, and the user's own resets. The button's bell is filled
 * when every reset reminds, and has a dot when only some do.
 */
export function ResetsMenu({ schedule }: { schedule: Schedule }) {
  const { resets, resetBells } = schedule;
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [when, setWhen] = useState<string>("daily"); // "daily" or a day key
  const [time, setTime] = useState("09:00");
  const [error, setError] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const all = resets.length > 0 && resets.every((r) => resetBells.has(r.id));
  const some = resetBells.size > 0 && !all;

  useEffect(() => {
    if (!open) return;
    const outside = (e: Event) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("pointerdown", outside);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("pointerdown", outside); window.removeEventListener("keydown", esc); };
  }, [open]);

  const add = () => {
    const message = schedule.addReset(name, when === "daily" ? "daily" : WEEKLY, when === "daily" ? undefined : when, time);
    setError(message ?? "");
    if (!message) setName("");
  };

  return (
    <div className="sch-links" ref={root}>
      <button className={`btn sch-linkbtn${open ? " on" : ""}${some ? " alert" : ""}`} aria-haspopup="dialog" aria-expanded={open}
        title="Откаты: время и напоминания" aria-label="Откаты: время, напоминания, свои откаты" onClick={() => setOpen(!open)}>
        <IconBell on={all} />Откаты
      </button>
      {open && (
        <div className="sch-linkmenu sch-resetmenu" role="dialog" aria-label="Откаты">
          <div className="head">
            <h3>Откаты</h3>
            <button className={`btn${all ? " primary" : ""}`} aria-pressed={all} onClick={schedule.toggleAllResets}
              title={all ? "Выключить напоминания обо всех откатах" : "Включить напоминания обо всех откатах"}>
              <IconBell on={all} />{all ? "Напоминаю обо всех" : "Напоминать обо всех"}
            </button>
          </div>
          <ul className="rows">
            {resets.map((r) => <ResetRow key={r.id} reset={r} schedule={schedule} />)}
          </ul>
          <div className="add">
            <label htmlFor="reset-name">Свой откат</label>
            <div className="field">
              <input id="reset-name" className="inp" value={name} placeholder="Название" maxLength={40}
                onChange={(e) => { setName(e.target.value); setError(""); }} onKeyDown={(e) => { if (e.key === "Enter") add(); }} />
            </div>
            <div className="field">
              <select className="inp" aria-label="Когда" value={when} onChange={(e) => setWhen(e.target.value)}>
                <option value="daily">Каждый день</option>
                {DAYS.map((d) => <option key={d} value={d}>{DAY_NAMES[d]}</option>)}
              </select>
              <input className="inp t" type="time" aria-label="Время по МСК" value={time} onChange={(e) => setTime(e.target.value)} />
              <button className="btn primary" onClick={add}><IconPlus />Добавить</button>
            </div>
            {error && <div className="err" role="alert">{error}</div>}
          </div>
          <p className="hint">Время по МСК, как на сервере. Изменённое время запоминается; кнопка со стрелкой возвращает время сервера.</p>
        </div>
      )}
    </div>
  );
}

function ResetRow({ reset, schedule }: { reset: Reset; schedule: Schedule }) {
  const [error, setError] = useState("");
  const bell = schedule.resetBells.has(reset.id);
  const set = (time: string, day?: string) => setError(schedule.editReset(reset, time, day) ?? "");
  return (
    <li className={bell ? "belled" : ""}>
      <div className="what">
        <b>{reset.name}</b>
        {reset.when === WEEKLY ? (
          <select className="inp" aria-label={`День: ${reset.name}`} value={reset.day} onChange={(e) => set(reset.time, e.target.value)}>
            {DAYS.map((d) => <option key={d} value={d}>{DAY_NAMES[d]}</option>)}
          </select>
        ) : <span className="muted">каждый день</span>}
      </div>
      <input className="inp t" type="time" aria-label={`Время: ${reset.name}`} value={reset.time} onChange={(e) => { if (e.target.value) set(e.target.value); }} />
      {reset.edited && <button className="btn icon" title="Вернуть время сервера" aria-label="Вернуть время сервера" onClick={() => set(serverTime(reset), serverDay(reset))}><IconReset /></button>}
      {reset.own && <button className="btn icon" title="Удалить откат" aria-label={`Удалить откат ${reset.name}`} onClick={() => schedule.removeReset(reset)}><IconClose /></button>}
      <button className={`btn icon bell${bell ? " on" : ""}`} aria-pressed={bell} title={bell ? "Не напоминать" : "Напоминать"} aria-label={`${bell ? "Не напоминать" : "Напоминать"}: ${reset.name}`}
        onClick={() => schedule.toggleResetBell(reset)}><IconBell on={bell} /></button>
      {error && <div className="err" role="alert">{error}</div>}
    </li>
  );
}

// The server's time and day of a reset: the original rows of data/schedule.json.
const ORIGINAL = (JSON.parse(scheduleText) as { resets: { time: string; day?: string }[] }).resets;
const serverTime = (r: Reset) => ORIGINAL[Number(r.id.slice(1))]?.time ?? r.time;
const serverDay = (r: Reset) => ORIGINAL[Number(r.id.slice(1))]?.day;
