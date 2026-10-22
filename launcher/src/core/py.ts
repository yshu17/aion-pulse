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

/** Python's float(): a number with optional sign, point and exponent, or inf / nan; anything else is null. */
export function pyFloat(text: string): number | null {
  const t = text.trim();
  if (/^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$/.test(t)) return Number(t);
  if (/^[+-]?(inf|infinity)$/i.test(t)) return t.startsWith("-") ? -Infinity : Infinity;
  if (/^[+-]?nan$/i.test(t)) return NaN;
  return null;
}

/** Python round(x) for a float: to the nearest integer, a tie goes to the even one (round(2.5) == 2). */
export function pyRound(x: number): number {
  const floor = Math.floor(x);
  const diff = x - floor; // exact for the magnitudes of the game
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** Python f"{x:.{digits}f}": the exact binary value rounded half-even (1.25 -> "1.2", which toFixed makes "1.3"). */
export function pyFixed(x: number, digits: number): string {
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, x);
  const bits = view.getBigUint64(0);
  const negative = bits >> 63n === 1n;
  const exponentBits = Number((bits >> 52n) & 0x7ffn);
  const fraction = bits & ((1n << 52n) - 1n);
  const mantissa = exponentBits === 0 ? fraction : fraction | (1n << 52n);
  const exponent = exponentBits === 0 ? -1074 : exponentBits - 1075;
  // x = mantissa * 2^exponent = n / 10^k exactly
  let n: bigint;
  let k: number;
  if (exponent >= 0) {
    n = mantissa << BigInt(exponent);
    k = 0;
  } else {
    n = mantissa * 5n ** BigInt(-exponent);
    k = -exponent;
  }
  let q: bigint;
  if (k > digits) {
    const unit = 10n ** BigInt(k - digits);
    q = n / unit;
    const twice = (n % unit) * 2n;
    if (twice > unit || (twice === unit && q % 2n === 1n)) q += 1n;
  } else {
    q = n * 10n ** BigInt(digits - k);
  }
  let text = q.toString().padStart(digits + 1, "0");
  if (digits > 0) text = text.slice(0, -digits) + "." + text.slice(-digits);
  return (negative && q !== 0n ? "-" : "") + text;
}

/** Python 3.12+ sum() of floats: Neumaier compensated summation, so the last bit matches CPython. */
export function pySum(values: Iterable<number>): number {
  let total = 0;
  let compensation = 0;
  for (const x of values) {
    const t = total + x;
    if (Math.abs(total) >= Math.abs(x)) compensation += total - t + x;
    else compensation += x - t + total;
    total = t;
  }
  return compensation && Number.isFinite(compensation) ? total + compensation : total;
}

/** Exact product as hi + lo (Dekker's split; what CPython gets from fma). */
function twoProduct(a: number, b: number): [number, number] {
  const split = (v: number): [number, number] => {
    const c = 134217729 * v; // 2^27 + 1
    const hi = c - (c - v);
    return [hi, v - hi];
  };
  const p = a * b;
  const [ah, al] = split(a);
  const [bh, bl] = split(b);
  return [p, ah * bh - p + ah * bl + al * bh + al * bl];
}

/** frexp(x)[1] for a positive normal x: the exponent e with x = m * 2^e, 0.5 <= m < 1. */
function frexpExponent(x: number): number {
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, x);
  return ((view.getUint16(0) >> 4) & 0x7ff) - 1022;
}

/**
 * Python math.hypot(*coordinates): CPython's vector_norm — exact scaling, error-free squares and sums, one correction
 * step — so the last bit matches (Math.hypot can differ by one ulp).
 */
export function pyHypot(...coordinates: number[]): number {
  const vec = coordinates.map(Math.abs);
  let max = 0;
  let foundNan = false;
  for (const x of vec) {
    if (Number.isNaN(x)) foundNan = true;
    else if (x > max) max = x;
  }
  if (max === Infinity) return Infinity;
  if (foundNan) return NaN;
  if (max === 0 || vec.length <= 1) return max;
  if (max < 2 ** -1022) return Math.hypot(...vec); // subnormal inputs: CPython rescales first; not met in the game
  const scale = 2 ** -frexpExponent(max);
  let csum = 1.0;
  let frac1 = 0.0;
  let frac2 = 0.0;
  const add = (hiSquare: number, loSquare: number) => {
    const sum = csum + hiSquare; // dl_fast_sum(csum, hi)
    const lo = hiSquare - (sum - csum);
    csum = sum;
    frac1 += loSquare;
    frac2 += lo;
  };
  for (const v of vec) {
    const x = v * scale;
    add(...twoProduct(x, x));
  }
  let h = Math.sqrt(csum - 1.0 + (frac1 + frac2));
  add(...twoProduct(-h, h));
  const x = csum - 1.0 + (frac1 + frac2);
  h += x / (2.0 * h); // differential correction
  return h / scale;
}
