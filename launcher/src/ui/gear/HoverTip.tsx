// The tooltip of the gear calculator (task 1 of docs/TASKS_TG_2026-11-18.md): it stands by the pointer and follows it
// (core/gear/tips.ts tipPlace keeps it inside the window), and says what «База данных» says. An item (a slot of the doll,
// a row of the list, a scroll) shows the same card as the database (CardBody); a skill or a buff shows the game's text of
// it (pulse.db by name, cleaned as the database cleans it), else the stats the calculator counts.
// `bind(info)` gives the props of the element, `box` is the box to render once.
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type FocusEvent, type MouseEvent } from "react";

import type { All } from "../../core/db/npcPoints";
import { skillText } from "../../core/db/gear";
import { itemByName } from "../../core/db/poiLinks";
import { tipPlace } from "../../core/gear/tips";
import { CardBody, StoneUi, useSpec, type StoneCard } from "../ItemCard";
import { Icon } from "../Icon";
import { SkillText } from "../SkillText";

export interface TipInfo {
  name: string; kind: string; icon: string | null; lines: string[];
  item?: { id: string; icon: string; grade: string; level?: number | null; kind?: string }; // an item: its database card
  byName?: boolean; // a scroll: its item is looked up by the name (its card when the database has it)
  stones?: StoneCard; // a slot of the doll: its stones in the card's squares and what they and the enchant add
}

const DELAY = 120; // the pointer rests this long before the box shows: passing over icons does not flash it

export function useHoverTip(all: All | null) {
  const [info, setInfo] = useState<TipInfo | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [itemId, setItemId] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const point = useRef<[number, number]>([0, 0]);
  const boxRef = useRef<HTMLDivElement>(null);
  const texts = useRef(new Map<string, string | null>());
  const items = useRef(new Map<string, string | null>());

  const place = useCallback(() => {
    const el = boxRef.current;
    if (!el) return;
    const { x, y } = tipPlace(point.current, [el.offsetWidth, el.offsetHeight], [window.innerWidth, window.innerHeight]);
    el.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
    el.style.visibility = "visible";
  }, []);
  // after every change of the content (a card loads and grows) the box is measured and placed again
  useLayoutEffect(place, [info, text, itemId, place]);
  useEffect(() => {
    if (!info) return;
    const el = boxRef.current;
    const grow = el && typeof ResizeObserver !== "undefined" ? new ResizeObserver(place) : null;
    if (el && grow) grow.observe(el);
    const gone = () => { window.clearTimeout(timer.current); setInfo(null); };
    window.addEventListener("scroll", gone, true); // a scrolled list moves the element away from the pointer
    window.addEventListener("pointerdown", gone, true);
    return () => { grow?.disconnect(); window.removeEventListener("scroll", gone, true); window.removeEventListener("pointerdown", gone, true); };
  }, [info, place]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const show = useCallback((tip: TipInfo) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      setInfo(tip);
      setText(null);
      setItemId(tip.item?.id ?? null);
      if (!all || tip.item) return;
      if (tip.byName) {
        if (items.current.has(tip.name)) { setItemId(items.current.get(tip.name) ?? null); return; }
        itemByName(all, tip.name).then((got) => { items.current.set(tip.name, got?.id ?? null); setItemId(got?.id ?? null); }).catch(() => {});
        return;
      }
      if (texts.current.has(tip.name)) { setText(texts.current.get(tip.name) ?? null); return; }
      skillText(all, tip.name).then((t) => { texts.current.set(tip.name, t); setText(t); }).catch(() => {});
    }, DELAY);
  }, [all]);
  const hide = useCallback(() => { window.clearTimeout(timer.current); setInfo(null); }, []);

  const bind = (tip: TipInfo) => ({
    onMouseEnter: (e: MouseEvent<HTMLElement>) => { point.current = [e.clientX, e.clientY]; show(tip); },
    onMouseMove: (e: MouseEvent<HTMLElement>) => { point.current = [e.clientX, e.clientY]; place(); },
    onMouseLeave: hide,
    onFocus: (e: FocusEvent<HTMLElement>) => { // the keyboard: by the element's corner
      const r = e.currentTarget.getBoundingClientRect();
      point.current = [r.right, r.top];
      show(tip);
    },
    onBlur: hide,
  });

  const box = info && (
    <div ref={boxRef} className={`gear-tip${itemId ? " card" : ""}`} role="tooltip" style={{ visibility: "hidden" }}>
      {itemId ? <ItemTip id={itemId} info={info} /> : (
        <>
          <header>
            {info.icon ? <Icon name={info.icon} size={36} /> : <span className="icon blank" style={{ width: 36, height: 36 }} />}
            <div><b>{info.name}</b><small>{info.kind}</small></div>
          </header>
          {text && <p className="txt"><SkillText text={text} /></p>}
          {!text && info.lines.length > 0 && <ul>{info.lines.map((l) => <li key={l}>{l}</li>)}</ul>}
        </>
      )}
    </div>
  );
  return { bind, box };
}

/** An item's tooltip: the card «База данных» shows for it. */
function ItemTip({ id, info }: { id: string; info: TipInfo }) {
  const answer = useSpec(id);
  const own = info.item;
  const card = <CardBody id={id} answer={answer} className="in-db"
    fallback={{ name: info.name, icon: own?.icon ?? info.icon ?? "", grade: own?.grade ?? "", level: own?.level, kind: own?.kind ?? info.kind }} />;
  return info.stones ? <StoneUi.Provider value={info.stones}>{card}</StoneUi.Provider> : card;
}
