import { useEffect, useRef, useState } from "react";

import { DAY_NAMES, LEADS, localZone, MSK_OFFSET } from "../../core/schedule/timing";
import { DAYS } from "../../core/schedule/reminders";
import { IconClose } from "../icons";
import { hm, toMinutes } from "./layout";
import { CHIP_TONE, CHIPS, Draft } from "./useSchedule";

const DAY_SHORT: Record<string, string> = { mon: "Пн", tue: "Вт", wed: "Ср", thu: "Чт", fri: "Пт", sat: "Сб", sun: "Вс" };
const SWATCH: Record<string, string> = { blue: "#6f9bff", green: "#5fd38d", teal: "#4fd1cf", amber: "#f5b544", purple: "#b58cff" };
const TIME = /^([01]?\d|2[0-3]):[0-5]\d$/;

interface Props {
  title: string;
  draft: Draft;
  /** «Новое событие»: the form next to the dragged card (floating) or a sheet from the bottom (narrow window). */
  placement: { kind: "float"; left: number; top: number } | { kind: "sheet" };
  onChange(draft: Draft): void;
  onSave(draft: Draft): void;
  onCancel(): void;
}

/** What is wrong with the draft, field by field (the messages stand under the field). */
export function problems(draft: Draft): { name?: string; time?: string; days?: string } {
  const out: { name?: string; time?: string; days?: string } = {};
  if (!draft.name.trim()) out.name = "Введи название события.";
  const start = TIME.test(draft.start);
  const end = TIME.test(draft.end) || draft.end === "24:00";
  if (!start || !end) out.time = "Время пиши как ЧЧ:ММ, например 18:30.";
  else if (toMinutes(draft.end) <= toMinutes(draft.start) && draft.end !== "00:00") out.time = "Конец должен быть позже начала. Событие до полуночи заканчивается в 24:00.";
  if (!draft.days.length) out.days = "Выбери хотя бы один день недели.";
  return out;
}

/** «18:00» MSK as the time of this computer, for the hint under the time fields. */
function localHint(draft: Draft): string {
  if (!TIME.test(draft.start) || !(TIME.test(draft.end) || draft.end === "24:00")) return "";
  const shift = localZone(Date.now()) - MSK_OFFSET; // minutes between this computer and Moscow
  const move = (t: string) => hm((((toMinutes(t) + shift) % 1440) + 1440) % 1440);
  return shift === 0 ? "это и твоё время" : `у тебя ${move(draft.start)}–${move(draft.end)}`;
}

export function EventForm({ title, draft, placement, onChange, onSave, onCancel }: Props) {
  const [tried, setTried] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const name = useRef<HTMLInputElement>(null);
  const bad = problems(draft);
  const set = (patch: Partial<Draft>) => onChange({ ...draft, ...patch });

  useEffect(() => { name.current?.focus(); name.current?.select(); }, []);

  const save = () => {
    setTried(true);
    if (Object.keys(bad).length === 0) onSave({ ...draft, name: draft.name.trim() });
  };
  const keys = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.stopPropagation(); onCancel(); }
    else if (e.key === "Enter" && (e.target as HTMLElement).tagName === "INPUT") { e.preventDefault(); save(); }
  };

  const style = placement.kind === "float" ? { left: placement.left, top: placement.top } : undefined;
  return (
    <>
      {placement.kind === "sheet" && <div className="sch-scrim" onClick={onCancel} />}
      <div ref={root} className={`sch-form ${placement.kind}`} style={style} role="dialog" aria-label={title} onKeyDown={keys}>
        {placement.kind === "sheet" && <div className="sch-grab" />}
        <h3>{title}<span className="spacer" />
          <button className="sch-x" aria-label="Закрыть форму" onClick={onCancel}><IconClose /></button></h3>

        <div className="f">
          <label htmlFor="ev-name">Название</label>
          <input id="ev-name" ref={name} className={`inp${tried && bad.name ? " bad" : ""}`} value={draft.name} maxLength={60}
            onChange={(e) => set({ name: e.target.value })} aria-invalid={Boolean(tried && bad.name)} aria-describedby="ev-name-err" />
          {tried && bad.name && <div id="ev-name-err" className="err" role="alert">{bad.name}</div>}
        </div>

        <div className="f">
          <label htmlFor="ev-start">Время</label>
          <div className="times">
            <input id="ev-start" className={`inp t${tried && bad.time ? " bad" : ""}`} value={draft.start} inputMode="numeric" maxLength={5}
              onChange={(e) => set({ start: e.target.value })} aria-label="Начало" />
            <span aria-hidden>—</span>
            <input className={`inp t${tried && bad.time ? " bad" : ""}`} value={draft.end} inputMode="numeric" maxLength={5}
              onChange={(e) => set({ end: e.target.value })} aria-label="Конец" />
            <span className="hint">МСК · {localHint(draft)}</span>
          </div>
          {tried && bad.time && <div className="err" role="alert">{bad.time}</div>}
        </div>

        <div className="f">
          <div className="label" id="ev-days">Повторять по дням</div>
          <div className="days" role="group" aria-labelledby="ev-days">
            {DAYS.map((d) => (
              <button key={d} type="button" className={draft.days.includes(d) ? "on" : ""} aria-pressed={draft.days.includes(d)} title={DAY_NAMES[d]}
                onClick={() => set({ days: draft.days.includes(d) ? draft.days.filter((x) => x !== d) : [...draft.days, d] })}>{DAY_SHORT[d]}</button>
            ))}
          </div>
          {tried && bad.days ? <div className="err" role="alert">{bad.days}</div> : <div className="hint">Событие повторяется каждую неделю в выбранные дни.</div>}
        </div>

        <div className="f">
          <div className="label" id="ev-group">Группа</div>
          <div className="opts" role="radiogroup" aria-labelledby="ev-group">
            {CHIPS.map((chip) => (
              <button key={chip} type="button" role="radio" aria-checked={draft.chip === chip} className={`o sw${draft.chip === chip ? " on" : ""}`}
                onClick={() => set({ chip })}><i style={{ background: SWATCH[CHIP_TONE[chip]] }} />{chip}</button>
            ))}
          </div>
        </div>

        <div className="f">
          <label className="bell-row">
            <input type="checkbox" checked={draft.bell} onChange={(e) => set({ bell: e.target.checked })} />
            <span className="box" /><span>Напоминать о событии</span>
          </label>
          {draft.bell && <LeadPicker value={draft.lead} onChange={(lead) => set({ lead })} />}
        </div>

        <div className="hint">Видно только тебе: расписание сервера не меняется.</div>
        <div className="actions">
          <button className="btn primary" onClick={save}>Сохранить</button>
          <button className="btn" onClick={onCancel}>Отменить</button>
          <span className="spacer" />
          <span className="hint">Enter — сохранить, Esc — отмена</span>
        </div>
      </div>
    </>
  );
}

/** «За сколько напомнить»: the reminder comes this many minutes before the start, and one more when it starts. */
export function LeadPicker({ value, onChange }: { value: number; onChange(minutes: number): void }) {
  const options = LEADS.some(([, m]) => m === value) ? LEADS : [...LEADS, [`${value} мин`, value] as [string, number]].sort((a, b) => a[1] - b[1]);
  return (
    <div className="lead">
      <span className="hint" id="lead-label">Напомнить за</span>
      <div className="segmented small" role="radiogroup" aria-labelledby="lead-label">
        {options.map(([label, minutes]) => (
          <button key={minutes} type="button" role="radio" aria-checked={value === minutes} className={value === minutes ? "on" : ""}
            onClick={() => onChange(minutes)}>{label}</button>
        ))}
      </div>
    </div>
  );
}
