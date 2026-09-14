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
