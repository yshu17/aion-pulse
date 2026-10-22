/**
 * Small Python behaviours the port must keep exactly: int(), str.split(), str.lower() for matching, modulo.
 * Used so the TypeScript core gives the same answers as core/ on the same input.
 */

export class PyValueError extends Error {}

/** Python int(): integers, truncated floats, booleans, digit strings (with spaces and a sign); anything else throws. */
export function pyInt(value: unknown): number {
  if (typeof value === "boolean") return value ? 1 : 0;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new PyValueError(`int(${value})`);
    return Math.trunc(value);
  }
  if (typeof value === "string" && /^\s*[+-]?\d+\s*$/.test(value)) return parseInt(value.trim(), 10);
  throw new PyValueError(`int(${JSON.stringify(value)})`);
}

/** Python «value or fallback»: None, False, 0, "" and empty lists are falsy. */
export function pyOr<T>(value: unknown, fallback: T): unknown {
  if (value === null || value === undefined || value === false || value === 0 || value === "") return fallback;
  if (Array.isArray(value) && value.length === 0) return fallback;
  return value;
}

/** Python str() of a JSON value (strings as they are, numbers, True / False). */
export function pyStr(value: unknown): string {
  if (typeof value === "boolean") return value ? "True" : "False";
  if (value === null || value === undefined) return "None";
  return String(value);
}

/** Python str.split() without arguments: split on any run of whitespace, no empty parts. */
export function pySplit(text: string): string[] {
  return text.split(/\s+/).filter((part) => part !== "");
}

/** Python a % n for a positive n (the result takes the sign of n). */
export function pyMod(a: number, n: number): number {
  return ((a % n) + n) % n;
}

/** Python str.casefold() for the alphabets of the game (Russian, English): lower case, «ß» as «ss». */
export function casefold(text: string): string {
  return text.toLowerCase().replace(/ß/g, "ss");
}
