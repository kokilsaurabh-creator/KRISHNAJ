import { useState } from "react";

import BankLedgerScreen from "./BankLedgerScreen";
import LedgerScreen from "./LedgerScreen";

type ReportTab = "party" | "bank";

const TABS: { value: ReportTab; label: string }[] = [
  { value: "party", label: "Party Ledger" },
  { value: "bank", label: "Bank Ledger" },
];

/** Thin wrapper: LedgerScreen (Party Ledger) is unchanged, just mounted
 * here alongside its new sibling. Neither sub-view knows the other
 * exists — bank_id lives only on payments and bank_ledger_entries, never
 * on ledger_entries, so Party Ledger has no bank reference to accidentally
 * leak by construction, not by a filter that could be forgotten. */
export default function ReportsScreen() {
  const [tab, setTab] = useState<ReportTab>("party");

  return (
    <div className="space-y-5">
      <div className="flex gap-2">
        {TABS.map((option) => {
          const selected = tab === option.value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={selected}
              onClick={() => setTab(option.value)}
              className={`min-h-[40px] flex-1 rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
                selected
                  ? "border-teal bg-teal-wash text-teal"
                  : "border-neutral-300 bg-white text-neutral-700 hover:border-neutral-400"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {tab === "party" ? <LedgerScreen /> : <BankLedgerScreen />}
    </div>
  );
}
