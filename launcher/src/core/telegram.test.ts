// Step 8 of the port: the Telegram batcher replays the Python golden scenarios (tools/golden_telegram.py).
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { ChatBatcher } from "./telegram/tgbatch";

const ROOT = join(__dirname, "..", "..", "..");
const golden = (name: string) => JSON.parse(readFileSync(join(ROOT, "tests", "golden", `${name}.json`), "utf-8")).case;

/** golden_telegram.make_line. */
function makeLine(kind: string, i: number, count: number): string {
  if (kind === "emoji") return "😀🔥".repeat(count) + ` #${i}`;
  if (kind === "sale") return `[${i}] Ник: продам 🗡️ меч +15, пишите в ЛС ` + "ё".repeat(count);
  return `[${i}] ` + "x".repeat(count);
}

/** golden_telegram._message: short messages in full, long ones as [characters, sha256]. */
function message(text: string): unknown {
  const chars = Array.from(text).length;
  return chars <= 300 ? text : [chars, createHash("sha256").update(text, "utf-8").digest("hex")];
}

const OPTION_NAMES: Record<string, string> = {
  warn_at: "warnAt", relax_below: "relaxBelow", window_sec: "windowSec", flush_after: "flushAfter", max_chars: "maxChars",
  max_queue: "maxQueue",
};

describe("telegram batcher", () => {
  it("packs, waits and backs off as in Python", () => {
    for (const { options, ops } of golden("telegram_batch").scenarios) {
      const b = new ChatBatcher(Object.fromEntries(Object.entries(options).map(([k, v]) => [OPTION_NAMES[k] ?? k, v])));
      ops.forEach((op: any[], step: number) => {
        const where = `${JSON.stringify(options)} step ${step}`;
        if (op[0] === "add") {
          b.add(makeLine(op[1][0], op[1][1], op[1][2]), op[2]);
        } else if (op[0] === "poll") {
          const sent = b.poll(op[1]).map(message);
          expect([sent, b.compact, b.batchSize, b.queued, b.dropped], where).toEqual(op.slice(2));
        } else {
          expect([b.nextSlotIn(op[1]), b.sentLastWindow(op[1])], where).toEqual(op.slice(2));
        }
      });
    }
  });
});
