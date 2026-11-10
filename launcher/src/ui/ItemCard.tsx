// The item card: a click on an item in the chat opens its description in the game's style (as Pulse's tooltip),
// next to the click; it stays until its cross or Esc, can be dragged by its title, and another item replaces it.
// In the program it is a window of its own (CardWindow.tsx), so it may stand outside the program's window; the plain
// browser (the dev page) shows it inside the page (ItemCard below).
import { m } from "motion/react";
import { createContext, Fragment, Ref, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";

import { Block, cardGrade, headBlocks, statValue } from "../core/items/card";
import { catalogById } from "./data";
import { FADE, SPRING } from "./fx";
import { Icon } from "./Icon";
import { IconClose } from "./icons";
import { itemSpec, SpecAnswer } from "./specs";
import "./itemCard.css";

export interface OpenCard { id: string; x: number; y: number }

/** Opens the card of an item at a point of the window (the click). */
export const OpenItem = createContext<(card: OpenCard) => void>(() => {});
export const useOpenItem = () => useContext(OpenItem);

/** The marks of a comparison (core/items/compare.ts): a stat's value is drawn better («up») or worse («dn»). */
export const StatMarks = createContext<Record<string, "up" | "dn">>({});

/** The rank line of a card made from the item's own row (its grade). */
const RANK: Record<string, string> = { junk: "Простой", common: "Обычный", rare: "Редкий", legend: "Легендарный", unique: "Уникальный",
  epic: "Эпический", mythic: "Мифический", finality: "Финальный" };

export const OFFSET = 18; // from the click, as in Pulse
const MARGIN = 8; // from the window's edges

/** The description of an item: null while it loads. */
export function useSpec(id: string): SpecAnswer | null {
  const [answer, setAnswer] = useState<SpecAnswer | null>(null);
  useEffect(() => {
    let alive = true;
    setAnswer(null);
    itemSpec(id).then((got) => { if (alive) setAnswer(got); });
    return () => { alive = false; };
  }, [id]);
  return answer;
}

/** Esc closes the card. */
export function useEsc(onClose: () => void): void {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
}

/** The card itself: its title (a drag handle) with the cross, the picture and the description blocks. */
export function CardBody({ id, answer, onClose, onDrag, cardRef, style, className = "", fallback }: {
  id: string; answer: SpecAnswer | null; onClose?(): void; onDrag?(e: React.PointerEvent): void;
  cardRef?: Ref<HTMLDivElement>; style?: React.CSSProperties; className?: string;
  /** The item's own row when the catalog has no card for it (the «База данных» tab): name, picture, grade. */
  fallback?: { name: string; icon: string; grade: string; level?: number | null; kind?: string };
}) {
  const item = catalogById[id] ?? fallback;
  const drag = onDrag ?? (() => {});
  const spec = answer?.spec ?? null;
  const name = spec?.name ?? item?.name ?? "Предмет";
  const grade = cardGrade(spec?.grade, item?.grade);
  const [copied, setCopied] = useState(false);
  useEffect(() => setCopied(false), [id]);
  const database = spec?.layout === "database";
  const empire = spec?.layout === "empire";
  const [head, rest] = headBlocks((spec?.blocks as Block[] | undefined) ?? []);
  return (
    <m.div ref={cardRef} className={`item-card ${className}${database ? " database" : ""}${empire ? " empire" : ""}`} role={onClose ? "dialog" : "region"} aria-label={name} style={style}
      initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.97, transition: FADE }}
      transition={{ ...SPRING, opacity: FADE }}>
      {empire ? <>
        <div className="ic-empire-title" onPointerDown={(e) => {
          if (e.button === 0 && !(e.target as HTMLElement).closest("button")) drag(e);
        }}>
          <b>{name}</b>
          {onClose && <button className="ic-x" aria-label="Закрыть" onClick={onClose}><IconClose /></button>}
        </div>
        <div className="ic-empire-tab">Общая информация</div>
        <div className="ic-empire-info">
          {item?.icon && <Icon name={item.icon} size={44} />}
          <div>
            <div className="ic-empire-rank"><span>Ранг</span><strong>{spec.rank ?? "[Обычный]"}</strong></div>
            <p>{(spec.restrictions as string[]).map((line) => `[${line}]`).join("; ")}</p>
          </div>
        </div>
        <hr className="ic-empire-rule" />
        <p className="ic-empire-description">{spec.description}</p>
      </> : database ? <>
        <div className="ic-title ic-db-heading" onPointerDown={(e) => {
          if (e.button === 0 && !(e.target as HTMLElement).closest("button")) drag(e);
        }}>
          {item?.icon && <Icon name={item.icon} size={56} />}
          <div className="ic-db-names">
            <b className={`ic-name g-${spec.title_grade ?? grade}`}>{name}</b>
            {spec.subtitle && <span>{spec.subtitle}</span>}
          </div>
          {onClose && <button className="ic-x" aria-label="Закрыть" onClick={onClose}><IconClose /></button>}
        </div>
        <dl className="ic-db-facts">
          {(spec.facts as [string, string][]).map(([label, value]) =>
            <div className="ic-db-row" key={label}><dt>{label}</dt><dd className={label === "Качество" ? `g-${grade}` : ""}>{value}</dd></div>)}
        </dl>
        {spec.restrictions?.length > 0 &&
          <div className="ic-db-restrictions">{(spec.restrictions as string[]).map((line) => <div key={line}>{line}</div>)}</div>}
        <div className="ic-db-description"><span>Описание</span><p>{spec.description}</p></div>
        <div className="ic-db-link">
          <code>{spec.item_link}</code>
          <button type="button" onClick={() => {
            if (navigator.clipboard?.writeText) {
              void navigator.clipboard.writeText(spec.item_link).then(() => setCopied(true));
            }
          }}>{copied ? "Скопировано" : "Копировать"}</button>
        </div>
      </> : <>
        <div className="ic-title" onPointerDown={(e) => { if (e.button === 0 && !(e.target as HTMLElement).closest("button")) drag(e); }}>
          <b className={`ic-name g-${grade}`}>{name}</b>
          {onClose && <button className="ic-x" aria-label="Закрыть" onClick={onClose}><IconClose /></button>}
        </div>
        <div className="ic-top">
          {item?.icon && <Icon name={item.icon} size={40} />}
          <div className="ic-head">
            {head.map((block, i) => <SpecBlock key={i} block={block} />)}
            {!answer && <div className="ic-text muted">Загружаю описание…</div>}
            {answer && !spec && fallback && !answer.error && <dl className="ic-pairs">
              <dt>Ранг</dt><dd>[{RANK[fallback.grade] ?? "Обычный"}]</dd>
              {fallback.kind && <><dt>Тип</dt><dd>{fallback.kind}</dd></>}
              {fallback.level ? <div className="ic-warning" style={{ gridColumn: "1 / -1" }}>Можно использовать с {fallback.level}-го уровня.</div> : null}
            </dl>}
            {answer && !spec && (!fallback || answer.error) && <div className="ic-text muted">{answer.error ? "Описание не загрузилось, открой карточку ещё раз." : "У этого предмета нет описания."}</div>}
          </div>
        </div>
        {rest.map((block, i) => <SpecBlock key={i} block={block} />)}
      </>}
    </m.div>
  );
}

/** The card inside the page (the plain browser): next to the click, kept inside the window, dragged by its title. */
export function ItemCard({ card, onClose }: { card: OpenCard; onClose(): void }) {
  const answer = useSpec(card.id);
  useEsc(onClose);
  const root = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<{ left: number; top: number } | null>(null);
  const fit = (left: number, top: number) => {
    const el = root.current!;
    return {
      left: Math.min(Math.max(MARGIN, left), Math.max(MARGIN, window.innerWidth - el.offsetWidth - MARGIN)),
      top: Math.min(Math.max(MARGIN, top), Math.max(MARGIN, window.innerHeight - el.offsetHeight - MARGIN)),
    };
  };
  useLayoutEffect(() => { // a new item: next to its click
    const width = root.current!.offsetWidth;
    const left = card.x + OFFSET + width <= window.innerWidth - MARGIN ? card.x + OFFSET : card.x - OFFSET - width;
    setAt(fit(left, card.y - 20));
  }, [card]); // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => { // the description came (taller card) or the window changed: still inside
    const keep = () => setAt((old) => (old ? fit(old.left, old.top) : old));
    keep();
    window.addEventListener("resize", keep);
    return () => window.removeEventListener("resize", keep);
  }, [answer]); // eslint-disable-line react-hooks/exhaustive-deps
  const drag = (e: React.PointerEvent) => {
    if (!at) return;
    const from = { x: e.clientX - at.left, y: e.clientY - at.top };
    const head = e.currentTarget as HTMLElement;
    head.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) => setAt(fit(ev.clientX - from.x, ev.clientY - from.y));
    const up = () => { head.removeEventListener("pointermove", move); head.removeEventListener("pointerup", up); };
    head.addEventListener("pointermove", move);
    head.addEventListener("pointerup", up);
  };
  return <CardBody id={card.id} answer={answer} onClose={onClose} onDrag={drag} cardRef={root} className="in-page"
    style={{ left: at?.left ?? -9999, top: at?.top ?? -9999 }} />;
}

/** One block of a description, drawn as watcher/tooltip.py does. */
function SpecBlock({ block }: { block: Block }) {
  const marks = useContext(StatMarks);
  const mark = (label: string) => (marks[label] ? `mark-${marks[label]}` : undefined);
  switch (block.kind) {
    case "hr":
      return <hr className="ic-hr" />;
    case "pairs":
      return (
        <dl className="ic-pairs">
          {(block.rows as [string, string][]).map(([label, value], i) => <Fragment key={i}><dt>{label}</dt><dd className={mark(label)}>{statValue(label, value)}</dd></Fragment>)}
        </dl>
      );
    case "props":
      return <>{(block.lines as string[]).map((line, i) => <div key={i} className="ic-props">{line}</div>)}</>;
    case "warning":
      return <div className="ic-warning">{block.text}</div>;
    case "grid":
      return (
        <dl className={`ic-grid${block.dim ? " dim" : ""}`}>
          {(block.pairs as [string, string][]).map(([label, value], i) => <Fragment key={i}><dt>{label}</dt><dd className={mark(label)}>{statValue(label, value)}</dd></Fragment>)}
        </dl>
      );
    case "text":
      return <p className={`ic-text ${block.style ?? "normal"}`}>{block.text}</p>;
    case "stones": {
      const bonus = block.bonus ?? 0;
      return (
        <div className="ic-stones" aria-label={`Гнёзд для камней: ${block.count}`}>
          {Array.from({ length: block.count as number }, (_, i) => i >= block.count - bonus
            ? <span key={i} className="bonus" title="Дополнительное гнездо: у предмета оно может быть, а может и не быть">?</span>
            : <span key={i} />)}
        </div>
      );
    }
    case "set":
      return <ul className="ic-set">{(block.items as string[]).map((name, i) => <li key={i}>{name}</li>)}</ul>;
    case "recipe":
      return (
        <>
          {(block.recipes as Record<string, any>[]).map((recipe, i) => (
            <div key={i} className="ic-recipe">
              <b>Создаётся по рецепту{recipe.skill ? `: ${recipe.skill}${recipe.level ? `, ${recipe.level}` : ""}` : ""}</b>
              <ul>{(recipe.ingredients as [string, number][]).map(([name, n], j) => <li key={j}>{name}{n > 1 ? `  ×${n}` : ""}</li>)}</ul>
              {recipe.count > 1 && <div className="ic-text muted">Создаётся предметов: {recipe.count}</div>}
            </div>
          ))}
        </>
      );
    default:
      return null;
  }
}
