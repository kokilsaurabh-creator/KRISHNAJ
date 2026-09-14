/**
 * Money display helpers.
 *
 * The API sends every amount as a JSON *string* (Decimal on the server,
 * never a float). Nothing here does arithmetic on those values — the
 * ledger's balances are computed server-side and displayed as received.
 * These functions only format for reading.
 */

const inr = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** "1234567.89" -> "12,34,567.89" (Indian grouping, no symbol). */
export function formatAmount(value: string | number): string {
  return inr.format(typeof value === "string" ? Number(value) : value);
}

/** "1234567.89" -> "₹12,34,567.89" */
export function formatCurrency(value: string | number): string {
  return `₹${formatAmount(value)}`;
}

const inrWhole = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** Like formatCurrency, but drops the paise on a whole amount:
 * "8550.00" -> "₹8,550", "1404.50" -> "₹1,404.50". For headline figures,
 * where a row of trailing zeros is noise. Ledger columns keep the paise. */
export function formatCurrencyTrim(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  return Number.isInteger(n) ? `₹${inrWhole.format(n)}` : formatCurrency(n);
}

export function isNegative(value: string): boolean {
  return value.trim().startsWith("-");
}

/** Drop a leading minus for display — direction is carried by Dr/Cr instead. */
export function absoluteAmount(value: string): string {
  return value.trim().replace(/^-/, "");
}

/**
 * Ledger sign convention (spec section 2): balance = SUM(debit) - SUM(credit),
 * so a positive balance is receivable (Dr) and a negative one is payable (Cr).
 * Dr/Cr is what carries the meaning in black-and-white print, where colour
 * is not available.
 */
export function balanceMarker(value: string): "Dr" | "Cr" {
  return isNegative(value) ? "Cr" : "Dr";
}

/** Formatted balance with its Dr/Cr marker, e.g. "12,34,567.89 Dr". */
export function formatBalance(value: string): string {
  return `${formatAmount(absoluteAmount(value))} ${balanceMarker(value)}`;
}

// ---- entry-form arithmetic ----
//
// The server recomputes every figure it stores, so nothing below is
// authoritative — it exists so the operator sees the same number while
// typing that the server will save. That only holds if the rounding
// matches, so these work in scaled integers rather than floats:
// 0.1 * 3 in binary floating point is 0.30000000000000004, and a jeweller
// reconciling a bill by hand will notice a stray paisa.

/** Decimal string -> integer count of its smallest unit, e.g. ("12.34", 2) -> 1234. */
function toScaledInt(value: string, places: number): number | null {
  const trimmed = value.trim();
  if (trimmed === "" || !/^-?\d*\.?\d*$/.test(trimmed)) return null;
  const negative = trimmed.startsWith("-");
  const [whole = "0", fraction = ""] = trimmed.replace("-", "").split(".");
  const padded = (fraction + "0".repeat(places)).slice(0, places);
  const scaled = Number(whole || "0") * 10 ** places + Number(padded || "0");
  return Number.isFinite(scaled) ? (negative ? -scaled : scaled) : null;
}

function fromCents(cents: number): string {
  const negative = cents < 0;
  const abs = Math.abs(cents);
  const body = `${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
  return negative ? `-${body}` : body;
}

/** quantity (3 dp) x rate (2 dp), rounded half-up to paise — the same
 * rounding the backend applies when it prices the line. */
export function lineAmount(quantity: string, rate: string): string {
  const q = toScaledInt(quantity, 3);
  const r = toScaledInt(rate, 2);
  if (q === null || r === null) return "0.00";
  // q is 1e-3 units and r is 1e-2 units, so the product is in 1e-5 units.
  return fromCents(Math.round((q * r) / 1000));
}

export function sumAmounts(values: string[]): string {
  return fromCents(values.reduce((total, v) => total + (toScaledInt(v, 2) ?? 0), 0));
}

export function subtractAmounts(a: string, b: string): string {
  return fromCents((toScaledInt(a, 2) ?? 0) - (toScaledInt(b, 2) ?? 0));
}

export function compareAmounts(a: string, b: string): number {
  return (toScaledInt(a, 2) ?? 0) - (toScaledInt(b, 2) ?? 0);
}

export function isValidDecimal(value: string, places: number): boolean {
  return toScaledInt(value, places) !== null;
}
