// «Энергокинез» and «Эфирокинез» under the right panel of a zone: the zone's gathering nodes (as aion-map.vercel.app),
// each section folds; a node switched on shows its spots on the map (MapTab draws them), its copy button puts all its
// spots on the clipboard as the game's place links, to paste in the chat (as the site).
import { useEffect, useRef, useState } from "react";

import { posLinks, type GatherNode } from "../../core/map/gathering";
import { plural } from "../../core/text";
import { IconCheck, IconChevron, IconCopy, IconEye } from "../icons";
import { gatherIcon } from "./mapData";

const SECTIONS = [["essence", "Энергокинез"], ["aether", "Эфирокинез"]] as const;

/** Text to the clipboard (the WebView2 of the program has navigator.clipboard; an old one: a hidden field). */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const field = document.createElement("textarea");
    field.value = text;
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    const done = document.execCommand("copy");
    field.remove();
    return done;
  }
}

export function GatherPanel({ nodes, mapId, shown, onToggle, onClear }: {
  nodes: { essence: GatherNode[]; aether: GatherNode[] }; mapId: string; shown: string[]; onToggle(id: string): void; onClear(): void;
}) {
  const [open, setOpen] = useState<string[]>([]);
  const [copied, setCopied] = useState<string | null>(null);
  const timer = useRef(0);
  useEffect(() => () => clearTimeout(timer.current), []);
  const copy = (key: string, text: string) => {
    copyText(text).then((done) => {
      if (!done) return;
      setCopied(key);
      clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(null), 1500);
    });
  };
  if (!nodes.essence.length && !nodes.aether.length) return null;
  const on = new Set(shown);
  const anyShown = [...nodes.essence, ...nodes.aether].some((n) => on.has(n.id));
  return (
    <section className="map-gather-panel" aria-label="Сбор ресурсов">
      <div className="map-gather-top">
        <h3>Сбор</h3>
        {anyShown && <button className="btn map-clear" onClick={onClear}>Скрыть все</button>}
      </div>
      {SECTIONS.map(([kind, title]) => {
        const list = nodes[kind];
        if (!list.length) return null;
        const isOpen = open.includes(kind);
        const count = list.filter((n) => on.has(n.id)).length;
        return (
          <div key={kind} className="map-gather-section">
            <button className="map-gather-head" aria-expanded={isOpen}
              onClick={() => setOpen((was) => (was.includes(kind) ? was.filter((k) => k !== kind) : [...was, kind]))}>
              <IconChevron open={isOpen} />
              <b>{title}</b>
              {count > 0 && <span className="map-gather-on">{count}</span>}
              <span className="muted">{list.length}</span>
            </button>
            {isOpen && (
              <ul className="map-gather-list">
                {list.map((n) => {
                  const src = gatherIcon(n.icon);
                  const pressed = on.has(n.id);
                  const key = `${n.id}:${n.layer ?? ""}`;
                  return (
                    <li key={key} className={pressed ? "on" : ""}>
                      <button className="map-gather-toggle" aria-pressed={pressed} onClick={() => onToggle(n.id)}
                        title={[n.name_en, plural(n.points.length, "точка", "точки", "точек")].filter(Boolean).join(" · ")}>
                        {src ? <img src={src} alt="" /> : <i />}
                        <span className="t"><span className="lvl">{n.level}</span> – {n.name}</span>
                        <span className="m">{n.points.length}</span>
                        <span className="eye" aria-hidden="true"><IconEye /></span>
                      </button>
                      <button className={`map-gather-copy${copied === key ? " done" : ""}`}
                        aria-label={`Копировать точки «${n.name}» ссылками для чата игры`} title="Копировать точки ссылками для чата игры"
                        onClick={() => copy(key, posLinks(n, mapId))}>
                        {copied === key ? <IconCheck /> : <IconCopy />}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </section>
  );
}
