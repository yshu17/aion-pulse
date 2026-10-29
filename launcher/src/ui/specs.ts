// An item's description for its card, from the worker that holds data/item_specs.json.gz (started on the first card).
import type { Spec } from "../core/items/specs";

export type SpecAnswer = { spec: Spec | null; error?: string };

let worker: Worker | null = null;
let asks = 0;
const waiting = new Map<number, (answer: SpecAnswer) => void>();

function start(): Worker {
  const started = new Worker(new URL("./specWorker.ts", import.meta.url), { type: "module" });
  started.onmessage = (event: MessageEvent<{ ask: number } & SpecAnswer>) => {
    const { ask, ...answer } = event.data;
    waiting.get(ask)?.(answer);
    waiting.delete(ask);
  };
  started.onerror = (event) => { // the worker itself failed: every open question gets an answer, the next one starts anew
    for (const answer of waiting.values()) answer({ spec: null, error: event.message || "worker" });
    waiting.clear();
    worker = null;
  };
  return started;
}

/** The description of an item, or null (with the error when the file could not be read). */
export function itemSpec(id: string): Promise<SpecAnswer> {
  worker ??= start();
  const ask = ++asks;
  return new Promise((resolve) => {
    waiting.set(ask, resolve);
    worker!.postMessage({ ask, id });
  });
}
