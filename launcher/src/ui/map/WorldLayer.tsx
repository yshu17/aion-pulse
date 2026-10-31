// The start screen of the «Карта» tab, as the game's world map: Atreia's globe (Asmodae, Elysea, the Abyss and
// Balaurea, the outer lands on the globe's rims), then a region with its zones. Hovering lights a part up, a click
// opens it. The globe, its highlights, the night sky and the names are those of aion-map.vercel.app
// (data/maps/world/site, atrea.json), Balaurea added on the rims; the regions are the game's own maps
// (tools/build_world_map.py -> data/maps/world).
import { useEffect, useMemo, useRef, useState } from "react";

import atreaJson from "../../../../data/maps/world/site/atrea.json?raw";
import worldJson from "../../../../data/maps/world/world.json?raw";
import { mapNames } from "../data";
import { pictureUrl } from "./mapData";

interface GlobePart { region: string; part: string; frame: [number, number, number, number]; up: string; over: string }
interface WorldZone {
  code: string; map_id: string | null; layer: number | null; frame: [number, number, number, number];
  highlight: [number, number, number, number] | null; highlight_file: string; label: [number, number, number, number] | null;
  icon?: string; // a zone the coloured map has no highlight for (the Silentera tunnel): the game's marker, lit on hover
  icon_size?: [number, number]; // its size in map units (44 × 44 without it)
}
interface Region { title: string; image: string; size: [number, number]; zones: WorldZone[] }
export const world = JSON.parse(worldJson) as { globe: { size: [number, number]; parts: GlobePart[] }; regions: Record<string, Region> };

interface AtreaImage { file: string; x: number; y: number; width: number; height: number; region?: string; emblem?: boolean }
const atrea = JSON.parse(atreaJson) as {
  viewBox: [number, number, number, number]; images: AtreaImage[]; paths: Record<string, string[]>;
  labels: { region: string; x: number; y: number; text: string; note?: string }[]; zone_names: Record<string, string>;
};
const ABYSS_NAMES = atrea.zone_names; // the Abyss layers named as on the site
const BG = "site/bg.png";
const TOP = 56; // the breadcrumb's band at the top of the map

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
  const bg = usePictures([BG])[BG];
  return (
    <div className="world-layer" style={bg ? { backgroundImage: `url(${bg})` } : undefined}>
      {region ? <RegionMap size={size} region={region} onZone={onZone} /> : <Globe size={size} onRegion={onRegion} />}
    </div>
  );
}

/** Atreia: the site's globe; a land lights up over its outline, Balaurea over the globe's rims (its own pixels). */
function Globe({ size, onRegion }: { size: { w: number; h: number }; onRegion(region: string): void }) {
  const [vx, vy, vw, vh] = atrea.viewBox;
  const files = useMemo(() => atrea.images.map((i) => `site/${i.file}`), []);
  const urls = usePictures(files);
  const rims = atrea.images.find((i) => i.region === "dragon")!;
  const masks = useMasks(urls, [`site/${rims.file}`]);
  const [hover, setHover] = useState<string | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  /** Balaurea under the mouse: a rim pixel of its picture (the lands' outlines are drawn over it and win). */
  const onRims = (e: React.PointerEvent | React.MouseEvent) => {
    const m = svg.current?.getScreenCTM();
    if (!m) return false;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    return opaque(masks[`site/${rims.file}`], (p.x - rims.x) / rims.width, (p.y - rims.y) / rims.height);
  };
  const scale = Math.max(0, Math.min((size.w - 40) / vw, (size.h - TOP - 10) / vh)); // a squeezed pane gives no negative size
  return (
    <svg ref={svg} className={`world-svg${hover ? " pointing" : ""}`} viewBox={`${vx} ${vy} ${vw} ${vh}`}
      width={vw * scale} height={vh * scale} role="group" aria-label="Атрея"
      onPointerMove={(e) => { if ((e.target as Element).tagName !== "path") setHover(onRims(e) ? "dragon" : null); }}
      onPointerLeave={() => setHover(null)}
      onClick={(e) => { if ((e.target as Element).tagName !== "path" && onRims(e)) onRegion("dragon"); }}>
      {atrea.images.map((i) => urls[`site/${i.file}`] && (
        <image key={i.file} href={urls[`site/${i.file}`]} x={i.x} y={i.y} width={i.width} height={i.height}
          className={i.emblem ? "world-emblem" : i.region ? `world-light${hover === i.region ? " on" : ""}` : undefined} />
      ))}
      {Object.entries(atrea.paths).map(([region, paths]) => paths.map((d, n) => (
        <path key={`${region}${n}`} d={d} className="world-hit" onPointerEnter={() => setHover(region)} onPointerLeave={() => setHover(null)}
          onClick={(e) => { e.stopPropagation(); onRegion(region); }} />
      )))}
      {atrea.labels.map((l) => (
        <g key={l.region} className={`world-name${hover === l.region ? " on" : ""}`} onPointerEnter={() => setHover(l.region)}
          onClick={(e) => { e.stopPropagation(); onRegion(l.region); }}>
          <text x={l.x} y={l.y}>{l.text}</text>
          {l.note && <text className="note" x={l.x} y={l.y + 16}>{l.note}</text>}
        </g>
      ))}
    </svg>
  );
}

/** A region: its map with each zone lit up on hover and named where the game names it. */
function RegionMap({ size, region, onZone }: { size: { w: number; h: number }; region: string; onZone(zone: WorldZone): void }) {
  const r = world.regions[region];
  const [rw, rh] = r.size;
  // under the breadcrumb (TOP), 20 px from the other edges; at most the pictures' own size (2x)
  const k = Math.max(0.01, Math.min((size.w - 40) / rw, (size.h - TOP - 20) / rh, 2));
  const left = (size.w - rw * k) / 2, top = TOP + (size.h - TOP - 20 - rh * k) / 2;
  const files = useMemo(() => [r.image, ...r.zones.flatMap((z) => [z.highlight_file, z.icon ?? ""]).filter(Boolean)], [r]);
  const urls = usePictures(files);
  const masks = useMasks(urls, r.zones.map((z) => z.highlight_file).filter(Boolean));
  const [hover, setHover] = useState<string | null>(null);
  const zoneAt = (e: { clientX: number; clientY: number; currentTarget: EventTarget }) => {
    const box = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const x = (e.clientX - box.left - left) / k, y = (e.clientY - box.top - top) / k;
    // the zone's own shape (its highlight), the smallest first; its button's box when the shape is not loaded
    const order = [...r.zones].sort((a, b) => a.frame[2] * a.frame[3] - b.frame[2] * b.frame[3]);
    for (const z of order) {
      const [hx, hy, hw, hh] = z.highlight ?? z.frame;
      const mask = z.highlight ? masks[z.highlight_file] : undefined;
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
        style={{ left, top, width: rw * k, height: rh * k }} />}
      {r.zones.map((z) => {
        const [hx, hy, hw, hh] = z.highlight ?? z.frame;
        return z.highlight_file && urls[z.highlight_file] ? (
          <img key={z.code} className={`world-zone-light${hover === z.code ? " on" : ""}`} src={urls[z.highlight_file]} alt="" draggable={false}
            style={{ left: left + hx * k, top: top + hy * k, width: hw * k, height: hh * k }} />
        ) : null;
      })}
      {r.zones.filter((z) => z.icon && urls[z.icon]).map((z) => {
        const [fx, fy, fw, fh] = z.frame;
        return <img key={`${z.code}-icon`} className={`world-zone-icon${hover === z.code ? " on" : ""}`} src={urls[z.icon!]} alt="" draggable={false}
          style={{ left: left + (fx + fw / 2) * k, top: top + (fy + fh / 2) * k, width: (z.icon_size?.[0] ?? 44) * k, height: (z.icon_size?.[1] ?? 44) * k }} />;
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
