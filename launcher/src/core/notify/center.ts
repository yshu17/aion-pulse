/**
 * Window-free notification center — the port of core/notify/notify_center.py.
 *
 * A presenter pulls queued events with popNext() and acknowledges them when the user reacts. Sources, sound,
 * counters, «не беспокоить», repeats and snoozes live here. The clock (seconds) and the sound player come in as
 * parameters; nothing here owns a timer: the caller calls tick().
 */

export interface NotificationAction {
  id: string;
  label: string;
}

export interface Notification {
  id: number;
  source: string;
  kind: string;
  title: string;
  text: string;
  actions: NotificationAction[];
  created_at: string; // ISO time of the wall clock, for the list only
  repeat_after: number | null;
  repeat_key: number | null;
  sound: boolean;
}

export interface SourceRule {
  enabled: boolean;
  sound: boolean;
}

export class NotifyError extends Error {}

export interface CenterOptions {
  sound?: (event: Notification) => void;
  clock?: () => number;
  wallClock?: () => Date;
  maxHistory?: number;
  maxQueue?: number;
}

export class NotificationCenter {
  rules = new Map<string, SourceRule>();
  do_not_disturb = false;
  history: Notification[] = [];
  readonly maxHistory: number;
  readonly maxQueue: number;
  private soundPlayer: (event: Notification) => void;
  private clock: () => number;
  private wallClock: () => Date;
  private queue: Notification[] = [];
  private counts = new Map<string, number>();
  private nextId = 1;
  private acknowledged = new Set<number>();
  private scheduled = new Map<number, [number, string]>(); // repeat key -> [deadline, "repeat" | "snooze"]
  private templates = new Map<number, Notification>();

  constructor(options: CenterOptions = {}) {
    this.maxHistory = options.maxHistory ?? 500;
    this.maxQueue = options.maxQueue ?? 100;
    if (this.maxHistory < 1 || this.maxQueue < 1) throw new NotifyError("history and queue limits must be positive");
    this.soundPlayer = options.sound ?? (() => {});
    this.clock = options.clock ?? (() => performance.now() / 1000);
    this.wallClock = options.wallClock ?? (() => new Date());
  }

  get queued(): number {
    return this.queue.length;
  }

  get unread(): number {
    return this.history.filter((e) => !this.acknowledged.has(e.repeat_key ?? e.id)).length;
  }

  /** The accepted event count, for one source or all. */
  count(source?: string): number {
    if (source !== undefined) return this.counts.get(source) ?? 0;
    let total = 0;
    for (const n of this.counts.values()) total += n;
    return total;
  }

  private rule(source: string): SourceRule {
    let rule = this.rules.get(source);
    if (rule === undefined) {
      rule = { enabled: true, sound: true };
      this.rules.set(source, rule);
    }
    return rule;
  }

  setSource(source: string, enabled: boolean | null = null, sound: boolean | null = null): void {
    const rule = this.rule(source);
    if (enabled !== null) rule.enabled = enabled;
    if (sound !== null) rule.sound = sound;
  }

  /** Record and queue a notification, or ignore it if its source is off. */
  notify(source: string, kind: string, title: string, text = "", actions: NotificationAction[] = [],
         sound = true, repeatAfter: number | null = null): Notification | null {
    if (!source || !kind || !title) throw new NotifyError("source, kind and title are required");
    if (repeatAfter !== null && repeatAfter <= 0) throw new NotifyError("repeat_after must be positive");
    const rule = this.rule(source);
    if (!rule.enabled) return null;
    const event = this.make(source, kind, title, text, [...actions], repeatAfter, null, sound);
    this.record(event, sound && rule.sound);
    if (!this.do_not_disturb) this.enqueue(event);
    if (repeatAfter !== null) {
      this.templates.set(event.id, event);
      this.scheduled.set(event.id, [this.clock() + repeatAfter, "repeat"]);
    }
    return event;
  }

  /** The next event for a presenter (e.g. the toast window). */
  popNext(): Notification | null {
    if (this.do_not_disturb) {
      this.queue = [];
      return null;
    }
    while (this.queue.length) {
      const event = this.queue.shift()!;
      if (this.isActive(event)) return event;
    }
    return null;
  }

  /** A presenter must hide a series accepted elsewhere or disabled later. */
  isActive(event: Notification): boolean {
    return !this.acknowledged.has(event.repeat_key ?? event.id) && (this.rules.get(event.source)?.enabled ?? true);
  }

  private find(id: number): Notification | undefined {
    for (let i = this.history.length - 1; i >= 0; i--) if (this.history[i].id === id) return this.history[i];
    return undefined;
  }

  /** Mark an event handled and cancel its pending repeat / snooze. */
  acknowledge(id: number): boolean {
    const event = this.find(id);
    if (event === undefined) return false;
    this.acknowledged.add(id);
    const key = event.repeat_key ?? event.id;
    this.acknowledged.add(key);
    this.scheduled.delete(key);
    this.templates.delete(key);
    this.queue = this.queue.filter((e) => (e.repeat_key ?? e.id) !== key);
    return true;
  }

  /** Show it once more after `seconds`; returns whether it was found. */
  snooze(id: number, seconds: number): boolean {
    if (seconds <= 0) throw new NotifyError("snooze duration must be positive");
    const event = this.find(id);
    if (event === undefined || !this.isActive(event)) return false;
    const key = event.repeat_key ?? event.id;
    this.templates.set(key, event);
    this.scheduled.set(key, [this.clock() + seconds, "snooze"]);
    this.queue = this.queue.filter((e) => (e.repeat_key ?? e.id) !== key);
    return true;
  }

  /** Emit due repeats and snoozes; call from the program's timer. Returns how many came out. */
  tick(): number {
    const now = this.clock();
    const due = [...this.scheduled].filter(([, [deadline]]) => deadline <= now).map(([key]) => key);
    let emitted = 0;
    for (const key of due) {
      this.scheduled.delete(key);
      if (this.acknowledged.has(key)) continue;
      const template = this.templates.get(key) ?? this.find(key);
      if (template === undefined) continue;
      const rule = this.rule(template.source);
      if (!rule.enabled) continue;
      const repeated = this.make(template.source, template.kind, template.title, template.text, template.actions,
        template.repeat_after, key, template.sound);
      this.record(repeated, rule.sound && template.sound);
      if (!this.do_not_disturb) this.enqueue(repeated);
      if (template.repeat_after !== null) this.scheduled.set(key, [now + template.repeat_after, "repeat"]);
      else this.templates.delete(key);
      emitted += 1;
    }
    return emitted;
  }

  private make(source: string, kind: string, title: string, text: string, actions: NotificationAction[],
               repeatAfter: number | null, repeatKey: number | null, sound: boolean): Notification {
    const event: Notification = {
      id: this.nextId, source, kind, title, text, actions, created_at: this.wallClock().toISOString(),
      repeat_after: repeatAfter, repeat_key: repeatKey || this.nextId, sound,
    };
    this.nextId += 1;
    return event;
  }

  private record(event: Notification, playSound: boolean): void {
    this.history.push(event);
    if (this.history.length > this.maxHistory) this.history.shift();
    this.counts.set(event.source, (this.counts.get(event.source) ?? 0) + 1);
    // keep the acknowledgement bookkeeping bounded alongside history
    const retained = new Set<number>();
    for (const e of this.history) retained.add(e.repeat_key ?? e.id);
    for (const e of this.queue) retained.add(e.repeat_key ?? e.id);
    for (const id of [...this.acknowledged]) if (!retained.has(id)) this.acknowledged.delete(id);
    if (playSound) this.soundPlayer(event);
  }

  private enqueue(event: Notification): void {
    if (this.queue.length >= this.maxQueue) this.queue.shift();
    this.queue.push(event);
  }
}
