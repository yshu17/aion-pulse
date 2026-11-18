/** The stigma calculator's English words (its data are from the NA client) in the Russian of the game's skill window. */

const KIND: Record<string, string> = { Normal: "Обычное", "Chain Skills": "Цепочка", Passive: "Пассивное" };
const TARGET: Record<string, string> = {
  "Selected Target": "Выбранная цель", Self: "На себя", "Area within a Radius of Target": "Область вокруг цели",
  "Group Member": "Член группы", Pet: "Питомец", "Specified Location": "Указанное место",
};
const INFO: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^Can jumpshot$/i, () => "Можно в прыжке"],
  [/^Can use while moving$/i, () => "Можно в движении"],
  [/^Max targets\s*=\s*(\d+)$/i, (m) => `Целей: до ${m[1]}`],
  [/^Damage in PVP\s*=\s*(\d+%)$/i, (m) => `Урон в PvP: ${m[1]}`],
  [/^Duration in PVP\s*=\s*(\d+%)$/i, (m) => `Длительность в PvP: ${m[1]}`],
  [/^Accuracy\s*=\s*([+-]?\d+)$/i, (m) => `Точность ${m[1]}`],
];

export const kindText = (kind: string) => KIND[kind] ?? kind;
export const targetText = (target: string) => TARGET[target] ?? target;

export function infoText(line: string): string {
  for (const [re, say] of INFO) {
    const m = line.trim().match(re);
    if (m) return say(m);
  }
  return line;
}

const comma = (n: string) => n.replace(".", ",");

export function castText(cast: string): string {
  if (/instant/i.test(cast)) return "мгновенно";
  const m = cast.match(/^([\d.]+)\s*s(?:ec)?$/i);
  return m ? `${comma(m[1])} с` : cast;
}

export function cooldownText(seconds: string): string {
  const s = Number(seconds);
  if (!seconds || !Number.isFinite(s)) return seconds;
  const min = Math.floor(s / 60), sec = s % 60;
  return min ? `${min} мин${sec ? ` ${sec} с` : ""}` : `${sec} с`;
}
