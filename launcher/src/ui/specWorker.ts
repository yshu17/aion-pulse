// The item descriptions (data/item_specs.json.gz: 0.7 MB packed, 22 MB of JSON) live in this worker: unpacked and
// parsed once, off the window's thread, then asked for one item at a time (specs.ts).
import specsUrl from "../../../data/item_specs.json.gz?url";
import { parseSpecs, SpecStore } from "../core/items/specs";

let store: Promise<SpecStore> | null = null;

async function load(): Promise<SpecStore> {
  const response = await fetch(specsUrl);
  if (!response.ok) throw new Error(`item_specs.json.gz: ${response.status}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  const packed = bytes[0] === 0x1f && bytes[1] === 0x8b; // a server may hand it over unpacked already
  const text = packed
    ? await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text()
    : new TextDecoder().decode(bytes);
  return parseSpecs(text);
}

self.onmessage = async (event: MessageEvent<{ ask: number; id: string }>) => {
  const { ask, id } = event.data;
  store ??= load();
  try {
    self.postMessage({ ask, spec: (await store).get(id) ?? null });
  } catch (error) {
    store = null; // the next card tries again
    self.postMessage({ ask, spec: null, error: String(error) });
  }
};
