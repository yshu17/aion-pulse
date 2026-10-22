"""Golden results of core/telegram/tgbatch.py for the TypeScript port (tests/golden/telegram_batch.json).

Each scenario is a list of operations on one ChatBatcher with the clock the scenario sets, and what came back. Lines
mix Cyrillic, emoji (two UTF-16 units each, one Python character) and very long text, so the 4096-character cut and
the packing count characters as Python does. Lines travel as recipes (make_line), long messages as digests.
"""

from __future__ import annotations

import hashlib
import random


def make_line(kind: str, i: int, count: int) -> str:
    """The test line a recipe stands for (the TypeScript test builds the same)."""
    if kind == "emoji":
        return "😀🔥" * count + f" #{i}"  # can be longer than a message: cut at max_chars characters
    if kind == "sale":
        return f"[{i}] Ник: продам 🗡️ меч +15, пишите в ЛС " + "ё" * count
    return f"[{i}] " + "x" * count


def _recipe(rnd: random.Random, i: int) -> list:
    kind = rnd.random()
    if kind < 0.04:
        return ["emoji", i, rnd.randint(500, 2200)]
    if kind < 0.25:
        return ["sale", i, rnd.randint(0, 900)]
    return ["plain", i, rnd.randint(1, 120)]


def _message(text: str):
    """Short messages in full; long ones as [length in characters, sha256 of UTF-8]."""
    return text if len(text) <= 300 else [len(text), hashlib.sha256(text.encode("utf-8")).hexdigest()]


def scenario(rnd: random.Random, options: dict, steps: int) -> dict:
    from core.telegram.tgbatch import ChatBatcher

    b = ChatBatcher(**options)
    now = 0.0
    n = 0
    ops = []
    for _ in range(steps):
        r = rnd.random()
        if r < 0.45:
            for _ in range(rnd.choice((1, 1, 2, 5, 25))):
                recipe = _recipe(rnd, n)
                n += 1
                b.add(make_line(*recipe), now)
                ops.append(["add", recipe, now])
        elif r < 0.85:
            ops.append(["poll", now, [_message(m) for m in b.poll(now)], b.compact, b.batch_size, b.queued, b.dropped])
        elif r < 0.95:
            ops.append(["slot", now, b.next_slot_in(now), b.sent_last_window(now)])
        now = round(now + rnd.choice((0.0, 0.5, 1.0, 2.9, 3.0, 3.1, 7.25, 20.0, 59.9, 60.0)), 2)
    ops.append(["poll", now, [_message(m) for m in b.poll(now)], b.compact, b.batch_size, b.queued, b.dropped])
    return {"options": options, "ops": ops}


def all_cases() -> dict[str, dict]:
    rnd = random.Random(20261022)
    configs = [{}, {"limit": 5, "warn_at": 4, "relax_below": 2, "window_sec": 10.0, "flush_after": 1.0},
               {"normal": 1, "compact": 3, "max_chars": 50, "max_queue": 7},
               {"limit": 3, "warn_at": 3, "relax_below": 3, "max_chars": 300, "flush_after": 0.0}]
    return {"telegram_batch": {"scenarios": [scenario(rnd, c, 300) for c in configs]}}
