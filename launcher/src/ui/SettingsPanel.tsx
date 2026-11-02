import { m } from "motion/react";
import { FADE, Glide, SPRING } from "./fx";
import { useEffect, useRef, useState } from "react";

import type { Config } from "../core/settings/config";
import { IconCheck, IconClose } from "./icons";
import type { Boot } from "./useBoot";
import { MAX_TOASTS_LIMIT } from "./useWatch";

const MEDIA = "C:\\Windows\\Media\\"; // the Windows sounds to choose from
const DEMO_SOUNDS = ["Alarm01.wav", "Windows Ding.wav", "Windows Exclamation.wav", "Windows Notify.wav"]; // the plain browser has no files
const OWN = "own"; // the choice «Свой файл…»: the path is typed in

const LEADS = [5, 10, 15, 30, 60]; // how many minutes before an event its reminder comes (unless the event has its own)

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
/** A sound to choose: the Windows signal, a sound of C:\Windows\Media, or an own WAV file (its path in a field under). */
function SoundPick({ id, label, path, sounds, onPath, onTry }: {
  id: string; label: string; path: string; sounds: string[]; onPath(path: string): void; onTry(): void;
}) {
  const known = path === "" || sounds.some((name) => MEDIA + name === path);
  const [own, setOwn] = useState(false); // «Свой файл…» chosen, the path still empty or being typed
  return (
    <>
      <div className="lbl"><label htmlFor={id}>{label}</label></div>
      <div className="row-field">
        <select id={id} className="field" value={own || !known ? OWN : path}
          onChange={(e) => { const v = e.target.value; setOwn(v === OWN); if (v !== OWN) onPath(v); }}>
          <option value="">Сигнал Windows</option>
          {sounds.map((name) => <option key={name} value={MEDIA + name}>{name.replace(/\.wav$/i, "")}</option>)}
          <option value={OWN}>Свой файл…</option>
        </select>
        <button className="btn" onClick={onTry}>Проверить</button>
      </div>
      {(own || !known) && (
        <input className="field" aria-label={`${label}: путь к своему файлу WAV`} value={path} autoFocus={own}
          placeholder="D:\Sounds\alert.wav" onChange={(e) => onPath(e.target.value)} />
      )}
    </>
  );
}

export function SettingsPanel({ boot, onClose, onTrySound }: { boot: Boot; onClose(): void; onTrySound(which: "match" | "notify"): void }) {
  const cfg = boot.config;
  const [word, setWord] = useState("");
  const [saved, setSaved] = useState(false);
  const [logState, setLogState] = useState<"checking" | "found" | "missing" | "browser">(boot.platform ? "checking" : "browser");
  const [sounds, setSounds] = useState<string[]>(boot.platform ? [] : DEMO_SOUNDS);
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

  useEffect(() => { boot.platform?.windowsSounds().then(setSounds).catch(() => setSounds([])); }, [boot.platform]);

  useEffect(() => { // is there a Chat.log at the path?
    const files = boot.platform;
    if (!files) return;
    setLogState("checking");
    files.fileSize(boot.chatLog).then(() => setLogState("found"), () => setLogState("missing"));
  }, [boot.platform, boot.chatLog]);

  // The parent re-renders every second (alert countdowns) and passes a new onClose each time: the panel must take
  // the focus once, when it opens, never again — or it pulls the focus out of the field being typed in.
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    panel.current?.focus();
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") close.current(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  return (
    <>
      <m.div className="scrim" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={FADE} />
      <m.aside className="panel" initial={{ x: 56, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 56, opacity: 0, transition: FADE }}
        transition={{ ...SPRING, opacity: FADE }} role="dialog" aria-label="Настройки" tabIndex={-1} ref={panel}>
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
            <SoundPick id="sound" label="Звук находки" path={cfg.sound_path} sounds={sounds}
              onPath={(path) => save({ sound_path: path })} onTry={() => onTrySound("match")} />
            <Toggle on={cfg.sound_loop} label="Повторять, пока не примешь" hint="звук находки звучит по кругу, пока совпадение ждёт «Принять»"
              onChange={(on) => save({ sound_loop: on })} />
            <SoundPick id="sound-notify" label="Звук уведомлений" path={cfg.notify_sound_path} sounds={sounds}
              onPath={(path) => save({ notify_sound_path: path })} onTry={() => onTrySound("notify")} />
            <div className="lbl"><label htmlFor="volume">Громкость</label></div>
            <div className="slider">
              <input id="volume" type="range" min={0} max={100} step={5} value={cfg.sound_volume}
                onChange={(e) => save({ sound_volume: Number(e.target.value) })} />
              <span>{cfg.sound_volume}%</span>
            </div>
            <Toggle on={cfg.notify_dnd} label="Не беспокоить" hint="без звука и всплывающих уведомлений"
              onChange={(on) => save({ notify_dnd: on })} />
            <Seconds value={cfg.notify_stack} label="Уведомлений на экране" hint="сколько тостов видно сразу: остальные ждут очереди и появляются по одному" min={1} max={MAX_TOASTS_LIMIT} unit="шт."
              onChange={(v) => save({ notify_stack: v })} />
            <div className="lbl"><span id="lead-all">Напоминать о событиях и откатах за</span></div>
            <div className="segmented" role="radiogroup" aria-labelledby="lead-all">
              {LEADS.map((minutes) => (
                <button key={minutes} type="button" role="radio" aria-checked={cfg.remind_min === minutes} className={cfg.remind_min === minutes ? "on" : ""}
                  onClick={() => save({ remind_min: minutes })}>{cfg.remind_min === minutes && <Glide group="seg-lead-all" />}<span>{minutes} мин</span></button>
              ))}
            </div>
            <div className="hint">У события можно поставить своё время в его форме.</div>
          </section>

          <section className="sec">
            <h3>Чат</h3>
            <Seconds value={cfg.chat_minutes} label="История при запуске" hint="сколько минут чата показать сразу" min={0} max={180}
              unit="мин" onChange={(v) => save({ chat_minutes: v })} />
            <Seconds value={cfg.chat_keep_min} label="Хранить сообщения" hint="через сколько минут старые сообщения исчезают из ленты (0 — не убирать)" min={0} max={180}
              unit="мин" onChange={(v) => save({ chat_keep_min: v })} />
          </section>

          <section className="sec last">
            <h3>Игра</h3>
            <Toggle on={cfg.game_check} label="Проверять, запущена ли игра" hint="нет процесса Aion — слежение останавливается и приходит уведомление"
              onChange={(on) => save({ game_check: on })} />
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
      </m.aside>
    </>
  );
}
