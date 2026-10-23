// «Игра запущена?»: what one check of the game process means, as in Pulse (watcher/app.py _game_closed).

/** true / false, or null when the process list could not be read. */
export type Game = boolean | null;

export const GAME_CHECK_SEC = 5; // while the program runs: how often to look for the game process

export interface GameStep {
  stop: boolean; // stop watching
  warn: boolean; // say «Игра не запущена» (once, until the game is back)
  clear: boolean; // the game is back (or the check is off): take the warning away
}

/**
 * A missing game stops the watching and warns once; a running game clears the warning. A check that is switched off
 * («game_check») or cannot read the process list never stops anything.
 */
export function gameStep(running: Game, enabled: boolean, watching: boolean, warned: boolean): GameStep {
  if (!enabled || running === null || running) return { stop: false, warn: false, clear: warned };
  return { stop: watching, warn: !warned, clear: false };
}
