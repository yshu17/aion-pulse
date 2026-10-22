// Step 4 of the port: core/notify replays the Python golden scenarios step by step.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { AlertBridge } from "./notify/bridge";
import { Notification, NotificationCenter, NotifyError } from "./notify/center";
import { releaseNotice, routeAction, scheduleCheckNotice } from "./notify/notices";
import { applyNotifySettings, CORNERS, DEFAULT_CORNER, DEFAULT_DURATION, DEFAULT_STACK, DURATIONS, SOURCES, STACK, ToastWindow } from "./notify/settings";
import { decide, fingerprint, knownFingerprint } from "./schedule/scheduleUpdate";
import { latestRelease, newer, parseVersion } from "./update/updater";

const ROOT = join(__dirname, "..", "..", "..");
const golden = (name: string) => JSON.parse(readFileSync(join(ROOT, "tests", "golden", `${name}.json`), "utf-8")).case;

/** A notification as the golden files keep it: without the wall-clock time, actions as [id, label]. */
function note(event: Notification | null) {
  if (event === null) return null;
  const { created_at: _created, ...rest } = event;
  return { ...rest, actions: event.actions.map((a) => [a.id, a.label]) };
}

describe("notification center", () => {
  const g = golden("notify_center");
  it("queue, history, repeats, snoozes and «не беспокоить» as in Python", () => {
    let clock = 0;
    const sounds: number[] = [];
    const c = new NotificationCenter({ sound: (e) => sounds.push(e.id), clock: () => clock, maxHistory: g.max_history,
      maxQueue: g.max_queue });
    for (const op of g.ops) {
      const want = op[op.length - 1];
      const where = JSON.stringify(op.slice(0, -1));
      let result: unknown;
      try {
        switch (op[0]) {
          case "notify":
            result = note(c.notify(op[1], op[2], op[3], op[4], op[5].map(([id, label]: string[]) => ({ id, label })), op[6], op[7]));
            break;
          case "pop": result = note(c.popNext()); break;
          case "source": c.setSource(op[1], op[2], op[3]); result = null; break;
          case "clock": clock = op[1]; result = null; break;
          case "tick": result = c.tick(); break;
          case "snooze": result = c.snooze(op[1], op[2]); break;
          case "ack": result = c.acknowledge(op[1]); break;
          case "dnd": c.do_not_disturb = op[1]; result = null; break;
          case "state":
            result = { queued: c.queued, unread: c.unread, history: c.history.map((e) => e.id),
              rules: Object.fromEntries([...c.rules].map(([k, r]) => [k, [r.enabled, r.sound]])) };
            break;
          case "counts":
            result = { all: c.count(), chat: c.count("chat"), schedule: c.count("schedule"), none: c.count("nope") };
            break;
          default: result = [...sounds];
        }
      } catch (error) {
        if (!(error instanceof NotifyError)) throw error;
        result = { error: error.message };
      }
      expect(result, where).toEqual(want);
    }
  });
});

describe("alert bridge", () => {
  const g = golden("notify_bridge");
  it("links chat alerts and notifications as in Python", () => {
    const c = new NotificationCenter({ clock: () => 0 });
    const b = new AlertBridge(c);
    const ops = g.ops;
    const n1 = b.chatMatch(ops[0][1], ops[0][2], ops[0][3]);
    expect(note(n1)).toEqual(ops[0][4]);
    expect(note(b.chatMatch(ops[1][1], ops[1][2], ops[1][3]))).toEqual(ops[1][4]);
    expect(note(b.chatMatch(ops[2][1], ops[2][2], ops[2][3]))).toEqual(ops[2][4]);
    const activeIds = () => c.history.filter((e) => c.isActive(e)).map((e) => e.id);
    expect(activeIds()).toEqual(ops[3][2]);
    b.alertsDone([1]);
    expect(c.history.map((e) => c.isActive(e))).toEqual(ops[4][1]);
    b.alertsDone([2]);
    expect(c.history.map((e) => c.isActive(e))).toEqual(ops[5][1]);
    const n3 = b.chatMatch(ops[6][1], ops[6][2], ops[6][3]);
    expect(note(n3)).toEqual(ops[6][4]);
    expect(b.toastAccepted(n3)).toEqual(ops[7][2]);
    expect(b.toastAccepted(n3)).toEqual(ops[8][2]);
    expect(b.toastAccepted(null)).toEqual(ops[9][1]);
    const g1 = b.gameRunning(false);
    expect(note(g1)).toEqual(ops[10][2]);
    expect(note(b.gameRunning(false))).toEqual(ops[11][2]);
    expect([note(b.gameRunning(true)), c.isActive(g1!)]).toEqual([ops[12][2], ops[12][3]]);
    expect(note(b.gameRunning(true))).toEqual(ops[13][2]);
    expect(note(b.gameRunning(false))).toEqual(ops[14][2]);
  });
});

describe("notification settings", () => {
  const g = golden("notify_settings");
  it("apply the same rules and window values", () => {
    expect([SOURCES, CORNERS, DURATIONS, STACK, [DEFAULT_CORNER, DEFAULT_DURATION, DEFAULT_STACK]])
      .toEqual([g.sources, g.corners, g.durations, g.stack, g.defaults]);
    for (const [cfg, rules, dnd, window] of g.cases) {
      const c = new NotificationCenter({ clock: () => 0 });
      const m: ToastWindow = { corner: null, duration: null, max_visible: null };
      applyNotifySettings(cfg, c, m);
      applyNotifySettings(cfg, c);
      expect(Object.fromEntries([...c.rules].map(([k, r]) => [k, [r.enabled, r.sound]]))).toEqual(rules);
      expect(c.do_not_disturb).toBe(dnd);
      expect([m.corner, m.duration, m.max_visible]).toEqual(window);
    }
  });
});

describe("notices, schedule check and versions", () => {
  const g = golden("notify_notices");
  it("decide the same notices", () => {
    for (const [found, can, current, seen, want] of g.release) {
      expect(releaseNotice(found, can, current, seen), JSON.stringify(found)).toEqual(want);
    }
    for (const [status, value, known, seen, manual, want] of g.schedule_check) {
      expect(scheduleCheckNotice(status, value, known, seen, manual)).toEqual(want);
    }
    for (const [action, key, rk, sk, want] of g.route) expect(routeAction(action, key, rk, sk)).toBe(want);
    for (const [k, cur, seen, m, want] of g.decide) expect(decide(k, cur, seen, m)).toBe(want);
    expect([fingerprint("https://x/a/schedule-20ru.jpg", '"e"', "Sun"),
      knownFingerprint({ image: "schedule-20ru.jpg", image_etag: '"e"', image_modified: "Sun" }), knownFingerprint({})])
      .toEqual(g.fingerprint);
    for (const [text, want] of g.versions) expect(parseVersion(text), text).toEqual(want);
    for (const [a, b, want] of g.newer) expect(newer(a, b), `${a} ${b}`).toBe(want);
    for (const [body, want] of g.latest) expect(latestRelease(body)).toEqual(want);
  });
});
