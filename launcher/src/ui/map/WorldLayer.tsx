// The start screen of the «Карта» tab, as the game's world map: Atreia's globe (Asmodae, Elysea, the Abyss and
// Balaurea, the outer lands on the globe's rims), then a region with its zones. Hovering lights a part up with the
// game's own «over» sprite, a click opens it. The pictures and the layout come from the client
// (tools/build_world_map.py -> data/maps/world); the parts are hit-tested by their pixels, not their boxes.
import { useEffect, useMemo, useRef, useState } from "react";

import worldJson from "../../../../data/maps/world/world.json?raw";
import { mapNames } from "../data";
import { pictureUrl } from "./mapData";

interface GlobePart { region: string; part: string; frame: [number, number, number, number]; up: string; over: string }
interface WorldZone {
  code: string; map_id: string | null; layer: number | null; frame: [number, number, number, number];
  highlight: [number, number, number, number] | null; highlight_file: string; label: [number, number, number, number] | null;
}
interface Region { title: string; image: string; size: number; zones: WorldZone[] }
export const world = JSON.parse(worldJson) as { globe: { size: [number, number]; parts: GlobePart[] }; regions: Record<string, Region> };

const ABYSS_NAMES: Record<string, string> = { ab1_1: "Нижний слой", ab1_2: "Ядро Бездны", ab1_3: "Верхний слой" };
const REGION_NOTE: Record<string, string> = { dragon: "внешние земли" };

/** The region a zone belongs to on the world map (null: a zone the world map has no place for, e.g. a temple). */
export function regionOf(mapId: string): string | null {
  return Object.entries(world.regions).find(([, r]) => r.zones.some((z) => z.map_id === mapId))?.[0] ?? null;
}

export const zoneTitle = (zone: WorldZone) => ABYSS_NAMES[zone.code] ?? (zone.map_id ? mapNames[zone.map_id] : zone.code) ?? zone.code;

/** The world pictures, read once (data/maps/world, as the zone pictures). */
function usePictures(files: string[]): Record<string, string> {
  const [urls, setUrls] = useState<Record<string, string>>({});
  useEffect(() => {
    let alive = true;
    for (const file of files) {
      pictureUrl(`world/${file}`).then((url) => { if (alive && url) setUrls((old) => ({ ...old, [file]: url })); });
    }
    return () => { alive = false; };
  }, [files.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
  return urls;
}

/** Alpha masks of pictures, to tell which part is under the mouse (the parts overlap as rectangles). */
function useMasks(urls: Record<string, string>, files: string[]): Record<string, ImageData> {
  const [masks, setMasks] = useState<Record<string, ImageData>>({});
  useEffect(() => {
    for (const file of files) {
      const url = urls[file];
      if (!url || masks[file]) continue;
      const image = new Image();
      image.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        const context = canvas.getContext("2d", { willReadFrequently: true });
        if (!context) return;
        context.drawImage(image, 0, 0);
        setMasks((old) => ({ ...old, [file]: context.getImageData(0, 0, canvas.width, canvas.height) }));
      };
      image.src = url;
    }
  }, [urls, files.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
  return masks;
}

/** Is the point (u, v) of a picture (0…1 of its width and height) opaque? Without a mask: inside the box is enough. */
function opaque(mask: ImageData | undefined, u: number, v: number): boolean {
  if (u < 0 || v < 0 || u >= 1 || v >= 1) return false;
  if (!mask) return true;
  const x = Math.floor(u * mask.width), y = Math.floor(v * mask.height);
  return mask.data[(y * mask.width + x) * 4 + 3] > 40;
}

export function WorldLayer({ size, region, onRegion, onZone }: {
  size: { w: number; h: number }; region: string | null; onRegion(region: string): void; onZone(zone: WorldZone): void;
}) {
  return region ? <RegionMap size={size} region={region} onZone={onZone} /> : <Globe size={size} onRegion={onRegion} />;
}

/** Atreia: the globe of five parts; Balaurea's two rims light up together. */
function Globe({ size, onRegion }: { size: { w: number; h: number }; onRegion(region: string): void }) {
  const [gw, gh] = world.globe.size;
  const k = Math.max(1, Math.min((size.w - 60) / gw, (size.h - 70) / gh));
  const left = (size.w - gw * k) / 2, top = (size.h - gh * k) / 2 + 10;
  const parts = world.globe.parts;
  const files = useMemo(() => parts.flatMap((p) => [p.up, p.over]), [parts]);
  const urls = usePictures(files);
  const masks = useMasks(urls, parts.map((p) => p.up));
  const [hover, setHover] = useState<string | null>(null);
  const hit = (e: { clientX: number; clientY: number; currentTarget: EventTarget }) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const x = (e.clientX - r.left - left) / k, y = (e.clientY - r.top - top) / k;
    for (const p of [...parts].reverse()) { // the topmost part first (the lands and the Abyss over the rims)
      const [fx, fy, fw, fh] = p.frame;
      if (opaque(masks[p.up], (x - fx) / fw, (y - fy) / fh)) return p.region;
    }
    return null;
  };
  const labels = Object.entries(world.regions).map(([key, r]) => {
    const own = parts.filter((p) => p.region === key);
    const p = key === "dragon" ? own.find((x) => x.part === "dragon2") ?? own[0] : own[0];
    const [fx, fy, fw, fh] = p.frame;
    // Balaurea: on the right of the upper rim, where no other name is
    const at = key === "dragon" ? [fx + fw * 0.93, fy + fh * 0.3] : [fx + fw / 2, fy + fh / 2];
    return { key, title: r.title, x: left + at[0] * k, y: top + at[1] * k };
  });
  return (
    <div className={`world-globe${hover ? " pointing" : ""}`} onPointerMove={(e) => setHover(hit(e))} onPointerLeave={() => setHover(null)}
      onClick={(e) => { const region = hit(e); if (region) onRegion(region); }} role="group" aria-label="Атрея">
      <div className="world-glow" style={{ left: size.w / 2, top: size.h / 2 + 10, width: gw * k * 1.15, height: gw * k * 1.15 }} />
      {parts.map((p) => {
        const [fx, fy, fw, fh] = p.frame;
        const style = { left: left + fx * k, top: top + fy * k, width: fw * k, height: fh * k };
        return (
          <div key={p.part} className={`world-part${hover === p.region ? " on" : ""}`} style={style}>
            {urls[p.up] && <img src={urls[p.up]} alt="" draggable={false} />}
            {urls[p.over] && <img className="over" src={urls[p.over]} alt="" draggable={false} />}
          </div>
        );
      })}
      {labels.map((l) => (
        <button key={l.key} className={`world-label${hover === l.key ? " on" : ""}`} style={{ left: l.x, top: l.y }}
          onPointerEnter={() => setHover(l.key)} onClick={(e) => { e.stopPropagation(); onRegion(l.key); }}>
          {l.title}{REGION_NOTE[l.key] && <small>{REGION_NOTE[l.key]}</small>}
        </button>
      ))}
    </div>
  );
}

/** A region: its map with each zone lit up on hover and named where the game names it. */
function RegionMap({ size, region, onZone }: { size: { w: number; h: number }; region: string; onZone(zone: WorldZone): void }) {
  const r = world.regions[region];
  const k = Math.min(size.w - 40, size.h - 40) / r.size;
  const left = (size.w - r.size * k) / 2, top = (size.h - r.size * k) / 2;
  const files = useMemo(() => [r.image, ...r.zones.map((z) => z.highlight_file)], [r]);
  const urls = usePictures(files);
  const masks = useMasks(urls, r.zones.map((z) => z.highlight_file));
  const [hover, setHover] = useState<string | null>(null);
  const zoneAt = (e: { clientX: number; clientY: number; currentTarget: EventTarget }) => {
    const box = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const x = (e.clientX - box.left - left) / k, y = (e.clientY - box.top - top) / k;
    // the zone's own shape (its highlight), the smallest first; its button's box when the shape is not loaded
    const order = [...r.zones].sort((a, b) => a.frame[2] * a.frame[3] - b.frame[2] * b.frame[3]);
    for (const z of order) {
      const [hx, hy, hw, hh] = z.highlight ?? z.frame;
      const mask = masks[z.highlight_file];
      if (mask ? opaque(mask, (x - hx) / hw, (y - hy) / hh)
        : x >= z.frame[0] && y >= z.frame[1] && x < z.frame[0] + z.frame[2] && y < z.frame[1] + z.frame[3]) return z;
    }
    return null;
  };
  const last = useRef<string | null>(null);
  return (
    <div className={`world-region${hover ? " pointing" : ""}`} role="group" aria-label={r.title}
      onPointerMove={(e) => { const z = zoneAt(e); const code = z?.map_id ? z.code : null; if (code !== last.current) { last.current = code; setHover(code); } }}
      onPointerLeave={() => { last.current = null; setHover(null); }}
      onClick={(e) => { const z = zoneAt(e); if (z?.map_id) onZone(z); }}>
      {urls[r.image] && <img className="world-region-map" src={urls[r.image]} alt="" draggable={false}
        style={{ left, top, width: r.size * k, height: r.size * k }} />}
      {r.zones.map((z) => {
        const [hx, hy, hw, hh] = z.highlight ?? z.frame;
        return urls[z.highlight_file] ? (
          <img key={z.code} className={`world-zone-light${hover === z.code ? " on" : ""}`} src={urls[z.highlight_file]} alt="" draggable={false}
            style={{ left: left + hx * k, top: top + hy * k, width: hw * k, height: hh * k }} />
        ) : null;
      })}
      {r.zones.filter((z) => z.map_id).map((z) => {
        const [lx, ly, lw, lh] = z.label ?? z.frame;
        return (
          <button key={z.code} className={`world-zone-name${hover === z.code ? " on" : ""}`}
            style={{ left: left + (lx + lw / 2) * k, top: top + (ly + lh / 2) * k }}
            onPointerEnter={() => { last.current = z.code; setHover(z.code); }} onClick={(e) => { e.stopPropagation(); onZone(z); }}>
            {zoneTitle(z)}
          </button>
        );
      })}
    </div>
  );
}

export type { WorldZone };
