// «Энергокинез» and «Эфирокинез» under the right panel of a zone: the zone's gathering nodes (as aion-map.vercel.app),
// each section folds; a node switched on shows its spots on the map (MapTab draws them).
import { useState } from "react";

import type { GatherNode } from "../../core/map/gathering";
import { plural } from "../../core/text";
import { IconChevron, IconEye } from "../icons";
import { gatherIcon } from "./mapData";

const SECTIONS = [["essence", "Энергокинез"], ["aether", "Эфирокинез"]] as const;

export function GatherPanel({ nodes, shown, onToggle, onClear }: {
  nodes: { essence: GatherNode[]; aether: GatherNode[] }; shown: string[]; onToggle(id: string): void; onClear(): void;
}) {
  const [open, setOpen] = useState<string[]>([]);
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
                  return (
                    <li key={`${n.id}:${n.layer ?? ""}`}>
                      <button className={pressed ? "on" : ""} aria-pressed={pressed} onClick={() => onToggle(n.id)}
                        title={`${n.name_en} · ${plural(n.points.length, "точка", "точки", "точек")}`}>
                        {src ? <img src={src} alt="" /> : <i />}
                        <span className="t"><span className="lvl">{n.level}</span> – {n.name}</span>
                        <span className="m">{n.points.length}</span>
                        <span className="eye" aria-hidden="true">{pressed && <IconEye />}</span>
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
