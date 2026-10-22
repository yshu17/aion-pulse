/**
 * Item spec (tooltip) data — the runtime part of core/items/specs.py (the KB page parser stays a Python tool).
 *
 * A spec is {name, grade, blocks: [...]}; block kinds pairs, props, warning, hr, grid, text, stones, set.
 * Values may be stored as JSON text and are parsed on first use. The caller un-gzips data/item_specs.json.gz.
 */

export type Spec = Record<string, any>;

export class SpecStore {
  private parsed = new Map<string, Spec>();

  constructor(private raw: Record<string, unknown> = {}) {}

  get size(): number {
    return Object.keys(this.raw).length;
  }

  has(id: string): boolean {
    return Object.prototype.hasOwnProperty.call(this.raw, id);
  }

  ids(): string[] {
    return Object.keys(this.raw);
  }

  get(id: string): Spec | undefined {
    if (!this.has(id)) return undefined;
    let spec = this.parsed.get(id);
    if (spec === undefined) {
      const value = this.raw[id];
      spec = (typeof value === "string" ? JSON.parse(value) : value) as Spec;
      this.parsed.set(id, spec);
    }
    return spec;
  }
}

/** The JSON text of item_specs.json -> SpecStore; null, broken or not an object gives an empty store. */
export function parseSpecs(text: string | null): SpecStore {
  try {
    const data = text === null ? null : JSON.parse(text);
    return new SpecStore(data && typeof data === "object" && !Array.isArray(data) ? data : {});
  } catch {
    return new SpecStore();
  }
}
