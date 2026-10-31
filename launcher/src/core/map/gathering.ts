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
}
