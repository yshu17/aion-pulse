// The tooltip of the gear calculator's skills, scrolls and buffs: the pointer over an icon shows the name, what it is, the
// game's text of it (pulse.db by name, as in «База данных»), else the stats the calculator counts. The box follows the icon
// and keeps out of the window's edge. `bind(info)` gives the props of the icon, `box` is the box to render once.
import { useCallback, useEffect, useRef, useState, type FocusEvent, type MouseEvent } from "react";
import { AnimatePresence, m } from "motion/react";

import type { All } from "../../core/db/npcPoints";
import { skillText } from "../../core/db/gear";
import { EASE } from "../fx";
import { Icon } from "../Icon";
import { SkillText } from "../SkillText";
import { cleanSkillText } from "../../core/items/statNames";

export interface TipInfo { name: string; kind: string; icon: string | null; lines: string[] }
interface Shown { info: TipInfo; x: number; y: number; flip: boolean }

const WIDTH = 300;

export function useHoverTip(all: All | null) {
  const [shown, setShown] = useState<Shown | null>(null);
  const [text, setText] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const texts = useRef(new Map<string, string | null>());
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const show = useCallback((info: TipInfo, target: HTMLElement) => {
    window.clearTimeout(timer.current);
    const r = target.getBoundingClientRect();
    const flip = r.right + WIDTH + 16 > window.innerWidth;
    timer.current = window.setTimeout(() => {
      setShown({ info, x: flip ? r.left - 8 : r.right + 8, y: Math.min(r.top, window.innerHeight - 260), flip });
      if (!all) { setText(null); return; }
      if (texts.current.has(info.name)) { setText(texts.current.get(info.name) ?? null); return; }
      setText(null);
      skillText(all, info.name).then((t) => { texts.current.set(info.name, t); setText((old) => (old === null ? t : old)); }).catch(() => {});
    }, 120);
  }, [all]);
  const hide = useCallback(() => { window.clearTimeout(timer.current); setShown(null); }, []);

  const bind = (info: TipInfo) => ({
    onMouseEnter: (e: MouseEvent<HTMLElement>) => show(info, e.currentTarget),
    onMouseLeave: hide,
    onFocus: (e: FocusEvent<HTMLElement>) => show(info, e.currentTarget),
    onBlur: hide,
  });

  const box = (
    <AnimatePresence>
      {shown && (
        <m.div key={shown.info.name} className="gear-tip" role="tooltip" style={{ left: shown.x, top: shown.y, translateX: shown.flip ? "-100%" : 0 }}
          initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.14, ease: EASE }}>
          <header>
            {shown.info.icon ? <Icon name={shown.info.icon} size={36} /> : <span className="icon blank" style={{ width: 36, height: 36 }} />}
            <div><b>{shown.info.name}</b><small>{shown.info.kind}</small></div>
          </header>
          {text && <p className="txt"><SkillText text={cleanSkillText(text)} /></p>}
          {!text && shown.info.lines.length > 0 && <ul>{shown.info.lines.map((l) => <li key={l}>{l}</li>)}</ul>}
        </m.div>
      )}
    </AnimatePresence>
  );
  return { bind, box };
}
