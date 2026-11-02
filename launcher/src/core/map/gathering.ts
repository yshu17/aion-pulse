/**
 * Gathering nodes of a zone (data/maps/gathering.json, from aion-map.vercel.app by tools/import_gathering.py): ore,
 * plants, fish … («Энергокинез», kind "essence") and aether («Эфирокинез», kind "aether"), each with its spots in game
 * coordinates. Pure: JSON in, lists out; broken or missing JSON gives no nodes.
 */

export interface GatherNode {
  id: string;
  name: string; // Russian, as the game
  name_en: string;
  kind: "essence" | "aether";
  type: string; // the site's kind: Metal, Herb, Fish, Aether …
  level: number;
  icon: string; // file name without .png in data/maps/gathering
  layer: number | null; // the Abyss layer, null elsewhere
  points: [number, number][]; // game x, y
}

/** A spot as the game writes a place link in its chat: «[pos:Адамантит;220040000 1225.0 492.9 0.0 0]» (no map id prefix). */
export const posLink = (name: string, mapId: string, [x, y]: [number, number]) =>
  `[pos:${name};${mapId} ${x.toFixed(1)} ${y.toFixed(1)} 0.0 0]`;

/** A resource found by name: where it grows (a zone, an Abyss layer) with the node of that place. */
export interface GatherHit {
  name: string;
  level: number;
  icon: string;
  kind: "essence" | "aether";
  places: { map_id: string; layer: number | null; node: GatherNode }[];
}

const fold = (text: string) => text.toLowerCase().replace(/ё/g, "е");

export class Gathering {
  private constructor(private readonly zones: Record<string, GatherNode[]>) {}

  static parse(text: string | null): Gathering {
    try {
      const data = JSON.parse(text ?? "") as { zones?: Record<string, GatherNode[]> };
      return new Gathering(data.zones ?? {});
    } catch {
      return new Gathering({});
    }
  }

  /** A zone's nodes on a layer (null: a zone without layers), energy and aether apart, each by level. */
  inZone(mapId: string, layer: number | null): { essence: GatherNode[]; aether: GatherNode[] } {
    const nodes = (this.zones[mapId] ?? []).filter((n) => n.layer === null || layer === null || n.layer === layer)
      .sort((a, b) => a.level - b.level || a.name.localeCompare(b.name, "ru"));
    return { essence: nodes.filter((n) => n.kind === "essence"), aether: nodes.filter((n) => n.kind === "aether") };
  }

  /**
   * Resources whose name (Russian or the site's English) has every word of the query, in any order; the same name and
   * level of all zones is one hit. Names starting with the first word come first, then by level and name. A query shorter than two letters finds nothing.
   */
  find(query: string, limit: number): GatherHit[] {
    const words = fold(query).split(/\s+/).filter(Boolean);
    if (!words.length || words.join("").length < 2) return [];
    const hits = new Map<string, GatherHit>();
    for (const [map_id, nodes] of Object.entries(this.zones)) {
      for (const node of nodes) {
        const text = `${fold(node.name)} ${fold(node.name_en)}`;
        if (!words.every((w) => text.includes(w))) continue;
        const key = `${node.level}|${node.name}`;
        const hit = hits.get(key) ?? { name: node.name, level: node.level, icon: node.icon, kind: node.kind, places: [] };
        hit.places.push({ map_id, layer: node.layer, node });
        hits.set(key, hit);
      }
    }
    const starts = (hit: GatherHit) => (fold(hit.name).startsWith(words[0]) ? 0 : 1); // «Рубин» before «Огромный рубин»
    return [...hits.values()].sort((a, b) => starts(a) - starts(b) || a.level - b.level || a.name.localeCompare(b.name, "ru")).slice(0, limit);
  }
}
