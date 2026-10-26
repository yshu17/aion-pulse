import { useEffect, useRef, useState } from "react";

import { IconExternal, IconLink, IconReset } from "../icons";
import { announce, useYields } from "./popover";
import type { Schedule } from "./useSchedule";

const BAD_ADDRESS = "Адрес должен начинаться с https:// и вести на сайт.";

/**
 * The link button of the schedule bar and its small menu: where the schedule is checked. One address, «Перейти» opens it,
 * «Проверить обновление» compares it with the saved state, «Сохранить» makes it the source and its current state the
 * schedule in use. The result of a check stands in the menu, and a dot on the button says when the link has changed.
 */
export function SourceMenu({ schedule }: { schedule: Schedule }) {
  const { site, source } = schedule;
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(source.url);
  const [error, setError] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const busy = site?.state === "busy";
  useYields("source", () => setOpen(false));

  useEffect(() => { setDraft(source.url); setError(""); }, [source.url]); // the saved link was read from the file or changed

  useEffect(() => {
    if (!open) return;
    field.current?.focus();
    field.current?.select();
    const outside = (e: Event) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("pointerdown", outside);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("pointerdown", outside); window.removeEventListener("keydown", esc); };
  }, [open]);

  const run = async (action: (text: string) => Promise<string | null>) => setError((await action(draft)) ?? "");
  const go = () => setError(schedule.openLink(draft) ? "" : BAD_ADDRESS);

  return (
    <div className="sch-links" ref={root}>
      <button className={`btn sch-linkbtn${open ? " on" : ""}${site?.state === "changed" ? " alert" : ""}`} aria-haspopup="dialog" aria-expanded={open}
        aria-label={site?.state === "changed" ? "Расписание на сайте обновилось: ссылка и проверка" : "Расписание на сайте: ссылка и проверка обновления"}
        title="Ссылка на расписание и проверка обновления" onClick={() => { if (!open) announce("source"); setOpen(!open); }}><IconLink /></button>
      {open && (
        <div className="sch-linkmenu" role="dialog" aria-label="Расписание на сайте">
          <h3>Расписание на сайте</h3>
          <label htmlFor="sch-source">Ссылка</label>
          <div className="ctl-row">
            <input id="sch-source" ref={field} className={`inp${error ? " bad" : ""}`} value={draft} placeholder="https://…" inputMode="url" spellCheck={false}
              aria-invalid={error !== ""} aria-describedby={error ? "sch-source-error" : undefined}
              onChange={(e) => { setDraft(e.target.value); setError(""); }}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); run(schedule.saveSource); } }} />
            <button className="btn sq" onClick={go} title="Перейти по ссылке" aria-label="Перейти по ссылке"><IconExternal /></button>
          </div>
          {error && <div id="sch-source-error" className="err" role="alert">{error}</div>}
          <div className="actions">
            <button className="btn" onClick={() => run(schedule.checkSource)} disabled={busy}><IconReset />{busy ? "Проверяю…" : "Проверить обновление"}</button>
            <button className="btn primary" onClick={() => run(schedule.saveSource)} disabled={busy}>Сохранить</button>
          </div>
          {site && <div className={`result ${site.state}`} role="status">{site.text}</div>}
          <p className="hint">Проверяется картинка расписания: ссылка на статью с картинкой или на саму картинку. Новую сетку пока вносим вручную.</p>
        </div>
      )}
    </div>
  );
}
