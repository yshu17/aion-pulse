// A skill's text with its numbers marked; the database's skill cards and the stigma calculator show it.
const NUMBER = /[+-]?\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?(?:\s*%|\s*ед\.(?:\s*урона)?|\s*сек\.?|\s*мин\.?|\s*м(?![а-яё]))?/gi;

/** A skill's text with every number that matters marked: damage, healing, range, time, percent («661-665 ед. урона», «25 м», «10 сек.», «+3%»). */
export function SkillText({ text }: { text: string }) {
  const parts: (string | { hit: string })[] = [];
  let from = 0;
  for (const m of text.matchAll(NUMBER)) {
    if (m.index > from) parts.push(text.slice(from, m.index));
    parts.push({ hit: m[0] });
    from = m.index + m[0].length;
  }
  if (from < text.length) parts.push(text.slice(from));
  return <>{parts.map((part, i) => (typeof part === "string" ? part : <b key={i} className="dbt-dmg">{part.hit}</b>))}</>;
}
