import { useEffect, useRef, useState } from "react";

import type { Config } from "../core/settings/config";
import { IconCheck, IconClose } from "./icons";
import type { Boot } from "./useBoot";

const MODES: [string, string, string][] = [
  ["or", "Слово или предмет", "любое из двух"], ["words", "Только слова", "предметы не важны"],
  ["items", "Только предметы", "слова не важны"], ["and", "Слово и предмет", "оба сразу"],
];

function Toggle({ on, label, hint, onChange }: { on: boolean; label: string; hint: string; onChange(on: boolean): void }) {
  return (
    <label className="sw">
      <span className="t"><b>{label}</b><span>{hint}</span></span>
      <input type="checkbox" role="switch" checked={on} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle" aria-hidden="true" />
    </label>
  );
}

function Seconds({ value, label, hint, min, max, unit = "с", onChange }: {
  value: number; label: string; hint: string; min: number; max: number; unit?: string; onChange(v: number): void;
}) {
  return (
    <label className="sw">
      <span className="t"><b>{label}</b><span>{hint}</span></span>
      <span className="num"><input type="number" min={min} max={max} value={value}
        onChange={(e) => { const v = Math.round(Number(e.target.value)); if (v >= min && v <= max) onChange(v); }} /><span>{unit}</span></span>
    </label>
  );
}

/** Settings slide in from the right; every change is saved at once (config.json). */
export function SettingsPanel({ boot, onClose, onTrySound }: { boot: Boot; onClose(): void; onTrySound(): void }) {
  const cfg = boot.config;
  const [word, setWord] = useState("");
  const [saved, setSaved] = useState(false);
  const [logState, setLogState] = useState<"checking" | "found" | "missing" | "browser">(boot.platform ? "checking" : "browser");
  const panel = useRef<HTMLDivElement>(null);
  const savedTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const save = (patch: Partial<Config>) => {
    boot.save(patch);
    setSaved(true);
    clearTimeout(savedTimer.current);
    savedTimer.current = setTimeout(() => setSaved(false), 1800);
  };
  const addWord = () => {
    const text = word.trim();
    if (text && !cfg.keywords.some((k) => k.toLowerCase() === text.toLowerCase())) save({ keywords: [...cfg.keywords, text] });
    setWord("");
  };

  useEffect(() => { // is there a Chat.log at the path?
    const files = boot.platform;
    if (!files) return;
    setLogState("checking");
    files.fileSize(boot.chatLog).then(() => setLogState("found"), () => setLogState("missing"));
  }, [boot.platform, boot.chatLog]);

  useEffect(() => {
    panel.current?.focus();
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="panel" role="dialog" aria-label="Настройки" tabIndex={-1} ref={panel}>
        <div className="ph">
          <h2>Настройки</h2>
          <span className={`saved${saved ? " on" : ""}`} aria-live="polite"><IconCheck />Сохранено</span>
          <span className="spacer" />
          <button className="btn icon-only" aria-label="Закрыть настройки" onClick={onClose}><IconClose /></button>
        </div>
        <div className="pb">
          <section className="sec">
            <h3>Что искать в чате</h3>
            <div className="lbl" id="kw-label">Ключевые слова</div>
            <div className="tags" aria-labelledby="kw-label">
              {cfg.keywords.map((k) => (
                <span key={k} className="tag">{k}
                  <button aria-label={`Убрать «${k}»`} onClick={() => save({ keywords: cfg.keywords.filter((x) => x !== k) })}><IconClose /></button>
                </span>
              ))}
              <input className="tag-input" value={word} placeholder="+ слово, Enter" aria-label="Новое ключевое слово"
                onChange={(e) => setWord(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addWord(); }
                  if (e.key === "Backspace" && !word && cfg.keywords.length) save({ keywords: cfg.keywords.slice(0, -1) });
                }} onBlur={addWord} />
            </div>
            <div className="hint">Большие и маленькие буквы не важны, «ё» = «е». Предметы отмечаются справа в «Что искать».</div>
            <div className="lbl">Как искать</div>
            <div className="modes" role="radiogroup" aria-label="Как искать">
              {MODES.map(([value, title, hint]) => (
                <button key={value} role="radio" aria-checked={cfg.search_mode === value}
                  className={`opt${cfg.search_mode === value ? " on" : ""}`} onClick={() => save({ search_mode: value })}>
                  <b>{title}</b><span>{hint}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="sec">
            <h3>Когда нашлось</h3>
            <Toggle on={cfg.alert_mode === "nag"} label="Ждать «Принять»" hint="совпадение ждёт ответа и считается принятым или пропущенным"
              onChange={(on) => save({ alert_mode: on ? "nag" : "standard" })} />
            <Seconds value={cfg.react_sec} label="Время на реакцию" hint="потом совпадение считается пропущенным" min={5} max={600}
              onChange={(v) => save({ react_sec: v })} />
            <Seconds value={cfg.cooldown_sec} label="Не повторять одно и то же" hint="тот же ник с тем же текстом" min={0} max={3600}
              onChange={(v) => save({ cooldown_sec: v })} />
          </section>

          <section className="sec">
            <h3>Звук и уведомления</h3>
            <div className="lbl"><label htmlFor="sound">Звук (файл WAV, пусто — сигнал Windows)</label></div>
            <div className="row-field">
              <input id="sound" className="field" value={cfg.sound_path} placeholder="C:\Windows\Media\Windows Exclamation.wav"
                onChange={(e) => save({ sound_path: e.target.value })} />
              <button className="btn" onClick={onTrySound}>Проверить звук</button>
            </div>
            <div className="lbl"><label htmlFor="volume">Громкость</label></div>
            <div className="slider">
              <input id="volume" type="range" min={0} max={100} step={5} value={cfg.sound_volume}
                onChange={(e) => save({ sound_volume: Number(e.target.value) })} />
              <span>{cfg.sound_volume}%</span>
            </div>
            <Toggle on={cfg.notify_dnd} label="Не беспокоить" hint="без звука и всплывающих уведомлений"
              onChange={(on) => save({ notify_dnd: on })} />
          </section>

          <section className="sec">
            <h3>Чат</h3>
            <Seconds value={cfg.chat_minutes} label="История при запуске" hint="сколько минут чата показать сразу" min={0} max={180}
              unit="мин" onChange={(v) => save({ chat_minutes: v })} />
          </section>

          <section className="sec last">
            <h3>Игра</h3>
            <div className="lbl"><label htmlFor="game">Папка игры</label></div>
            <input id="game" className="field" value={cfg.game_dir} onChange={(e) => save({ game_dir: e.target.value })} />
            <div className="lbl"><label htmlFor="log">Chat.log (если лежит не в папке игры)</label></div>
            <input id="log" className="field" value={cfg.chat_log} placeholder={`${cfg.game_dir}\\classic\\Chat.log`}
              onChange={(e) => save({ chat_log: e.target.value })} />
            <div className={`hint log-${logState}`}>
              {logState === "found" ? `Chat.log найден: ${boot.chatLog}` : logState === "missing"
                ? `Не найден: ${boot.chatLog}. Проверь папку игры.` : logState === "checking" ? "Проверяю…" : "В браузере файлов нет: демо-чат"}
            </div>
          </section>
        </div>
      </aside>
    </>
  );
}
