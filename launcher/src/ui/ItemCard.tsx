// The item card: a click on an item in the chat opens its description in the game's style (as Pulse's tooltip),
// next to the click; it stays until its cross or Esc, can be dragged by its title, and another item replaces it.
import { m } from "motion/react";
import { createContext, Fragment, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";

import { Block, cardGrade, headBlocks } from "../core/items/card";
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

const OFFSET = 18; // from the click, as in Pulse
const MARGIN = 8; // from the window's edges

export function ItemCard({ card, onClose }: { card: OpenCard; onClose(): void }) {
  const item = catalogById[card.id];
  const [answer, setAnswer] = useState<SpecAnswer | null>(null);
  useEffect(() => {
    let alive = true;
    setAnswer(null);
    itemSpec(card.id).then((got) => { if (alive) setAnswer(got); });
    return () => { alive = false; };
  }, [card.id]);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  // place: right of the click (left when there is no room), kept inside the window; a drag moves it from there
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
    if ((e.target as HTMLElement).closest("button") || !at) return;
    const from = { x: e.clientX - at.left, y: e.clientY - at.top };
    const head = e.currentTarget as HTMLElement;
    head.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) => { setAt(fit(ev.clientX - from.x, ev.clientY - from.y)); };
    const up = () => { head.removeEventListener("pointermove", move); head.removeEventListener("pointerup", up); };
    head.addEventListener("pointermove", move);
    head.addEventListener("pointerup", up);
  };

  const spec = answer?.spec ?? null;
  const name = spec?.name ?? item?.name ?? "Предмет";
  const grade = cardGrade(spec?.grade, item?.grade);
  const [head, rest] = headBlocks((spec?.blocks as Block[] | undefined) ?? []);
  return (
    <m.div ref={root} className="item-card" role="dialog" aria-label={name}
      style={{ left: at?.left ?? -9999, top: at?.top ?? -9999 }}
      initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.97, transition: FADE }}
      transition={{ ...SPRING, opacity: FADE }}>
      <div className="ic-title" onPointerDown={drag}>
        <b className={`ic-name g-${grade}`}>{name}</b>
        <button className="ic-x" aria-label="Закрыть" onClick={onClose}><IconClose /></button>
      </div>
      <div className="ic-top">
        {item?.icon && <Icon name={item.icon} size={40} />}
        <div className="ic-head">
          {head.map((block, i) => <SpecBlock key={i} block={block} />)}
          {!answer && <div className="ic-text muted">Загружаю описание…</div>}
          {answer && !spec && <div className="ic-text muted">{answer.error ? "Описание не загрузилось, открой карточку ещё раз." : "У этого предмета нет описания."}</div>}
        </div>
      </div>
      {rest.map((block, i) => <SpecBlock key={i} block={block} />)}
    </m.div>
  );
}

/** One block of a description, drawn as watcher/tooltip.py does. */
function SpecBlock({ block }: { block: Block }) {
  switch (block.kind) {
    case "hr":
      return <hr className="ic-hr" />;
    case "pairs":
      return (
        <dl className="ic-pairs">
          {(block.rows as [string, string][]).map(([label, value], i) => <Fragment key={i}><dt>{label}</dt><dd>{value}</dd></Fragment>)}
        </dl>
      );
    case "props":
      return <>{(block.lines as string[]).map((line, i) => <div key={i} className="ic-props">{line}</div>)}</>;
    case "warning":
      return <div className="ic-warning">{block.text}</div>;
    case "grid":
      return (
        <dl className={`ic-grid${block.dim ? " dim" : ""}`}>
          {(block.pairs as [string, string][]).map(([label, value], i) => <Fragment key={i}><dt>{label}</dt><dd>{value}</dd></Fragment>)}
        </dl>
      );
    case "text":
      return <p className={`ic-text ${block.style ?? "normal"}`}>{block.text}</p>;
    case "stones": {
      const bonus = block.bonus ?? 0;
      return (
        <div className="ic-stones" aria-label={`Гнёзд для камней: ${block.count}`}>
          {Array.from({ length: block.count as number }, (_, i) => <span key={i} className={i >= block.count - bonus ? "bonus" : ""} />)}
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
