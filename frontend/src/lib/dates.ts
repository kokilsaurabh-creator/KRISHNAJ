/** Indian financial year runs April–March, matching the backend's
 * fiscal_year_for() in app/services/doc_numbering.py. */

const FY_START_MONTH = 3; // JS months are 0-based, so 3 = April

export type DateRange = { from: string; to: string };

export type PresetKey = "this_month" | "this_fy" | "last_fy" | "custom";

export const PRESET_LABELS: Record<PresetKey, string> = {
  this_month: "This month",
  this_fy: "This FY",
  last_fy: "Last FY",
  custom: "Custom",
};

function iso(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Calendar year in which the financial year containing `d` started. */
export function fyStartYear(d: Date): number {
  return d.getMonth() >= FY_START_MONTH ? d.getFullYear() : d.getFullYear() - 1;
}

/** e.g. 2026 -> "2026-27", matching the backend's document-number format. */
export function fyLabel(startYear: number): string {
  return `${startYear}-${String(startYear + 1).slice(-2)}`;
}

export function thisMonth(today = new Date()): DateRange {
  const from = new Date(today.getFullYear(), today.getMonth(), 1);
  const to = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  return { from: iso(from), to: iso(to) };
}

export function financialYear(startYear: number): DateRange {
  return {
    from: iso(new Date(startYear, FY_START_MONTH, 1)),
    to: iso(new Date(startYear + 1, FY_START_MONTH, 0)),
  };
}

export function thisFY(today = new Date()): DateRange {
  return financialYear(fyStartYear(today));
}

export function lastFY(today = new Date()): DateRange {
  return financialYear(fyStartYear(today) - 1);
}

export function rangeForPreset(preset: PresetKey, today = new Date()): DateRange {
  switch (preset) {
    case "this_month":
      return thisMonth(today);
    case "this_fy":
      return thisFY(today);
    case "last_fy":
      return lastFY(today);
    default:
      return thisFY(today);
  }
}

/** "2026-04-05" -> "05 Apr 2026", for reading rather than sorting. */
export function formatDisplayDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}
