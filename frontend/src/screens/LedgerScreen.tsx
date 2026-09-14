import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import DateRangePicker from "../components/DateRangePicker";
import PartyPicker from "../components/PartyPicker";
import { api, TXN_TYPE_LABELS, type Ledger, type LedgerRow, type Party } from "../lib/api";
import { formatDisplayDate, thisFY, type DateRange, type PresetKey } from "../lib/dates";
import { downloadLedgerPdf } from "../lib/ledgerPdf";
import { absoluteAmount, balanceMarker, formatAmount, isNegative } from "../lib/money";

/** Receivable reads teal, payable reads red — and Dr/Cr repeats it in text
 * so the meaning survives a black-and-white printout. */
function BalanceText({ value, className = "" }: { value: string; className?: string }) {
  const negative = isNegative(value);
  return (
    <span className={`amount ${negative ? "text-danger" : "text-teal"} ${className}`}>
      {formatAmount(absoluteAmount(value))}
      <span className="ml-1 text-[0.75em] font-medium opacity-80">{balanceMarker(value)}</span>
    </span>
  );
}

function SummaryFigure({ label, value, sublabel }: { label: string; value: string; sublabel: string }) {
  return (
    <div className="rounded-xl border border-neutral-200 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold">
        <BalanceText value={value} />
      </p>
      <p className="mt-0.5 text-xs text-neutral-500">{sublabel}</p>
    </div>
  );
}

/** Receipts and payments read peacock; sales and purchases stay neutral. */
function typeClass(type: LedgerRow["type"]): string {
  return type === "receipt" || type === "payment" ? "text-peacock" : "text-neutral-700";
}

export default function LedgerScreen() {
  const [party, setParty] = useState<Party | null>(null);
  const [preset, setPreset] = useState<PresetKey>("this_fy");
  const [range, setRange] = useState<DateRange>(() => thisFY());
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const validRange = range.from !== "" && range.to !== "" && range.from <= range.to;

  const { data, isPending, isError, error } = useQuery({
    queryKey: ["ledger", party?.id, range.from, range.to],
    queryFn: () =>
      api.get<Ledger>(`/ledger/${party!.id}?from=${range.from}&to=${range.to}`),
    enabled: party !== null && validRange,
  });

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-neutral-900">Ledger</h2>
        <p className="text-sm text-neutral-600">Statement of account for one party over a period.</p>
      </div>

      <section className="space-y-4 rounded-xl border border-neutral-200 p-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-neutral-700">Party</label>
          <PartyPicker value={party} onChange={setParty} />
        </div>

        <div>
          <span className="mb-1.5 block text-sm font-medium text-neutral-700">Period</span>
          <DateRangePicker
            preset={preset}
            range={range}
            onChange={(nextPreset, nextRange) => {
              setPreset(nextPreset);
              setRange(nextRange);
            }}
          />
        </div>

        {!validRange && (
          <p role="alert" className="text-sm text-danger">
            The “from” date must be on or before the “to” date.
          </p>
        )}
      </section>

      {party === null && (
        <p className="rounded-xl border border-dashed border-neutral-300 px-4 py-8 text-center text-sm text-neutral-500">
          Search for a party above to view its ledger.
        </p>
      )}

      {party !== null && isPending && validRange && (
        <p className="px-4 py-8 text-center text-sm text-neutral-500">Loading ledger…</p>
      )}

      {isError && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {error instanceof Error ? error.message : "Could not load the ledger."}
        </p>
      )}

      {data && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <SummaryFigure
              label="Opening"
              value={data.opening}
              sublabel={`As on ${formatDisplayDate(data.from_date)}`}
            />
            <SummaryFigure
              label="Closing"
              value={data.closing}
              sublabel={`As on ${formatDisplayDate(data.to_date)}`}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-neutral-600">
              {data.rows.length === 0
                ? "No transactions in this period"
                : `${data.rows.length} ${data.rows.length === 1 ? "transaction" : "transactions"}`}
            </p>
            <button
              type="button"
              className="btn-secondary"
              disabled={exporting}
              onClick={async () => {
                setExportError(null);
                setExporting(true);
                try {
                  await downloadLedgerPdf(data);
                } catch {
                  setExportError("Could not generate the PDF. Please try again.");
                } finally {
                  setExporting(false);
                }
              }}
            >
              {exporting ? "Preparing PDF…" : "Export PDF"}
            </button>
          </div>

          {exportError && (
            <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
              {exportError}
            </p>
          )}

          {data.rows.length === 0 ? (
            <div className="rounded-xl border border-dashed border-neutral-300 px-4 py-10 text-center">
              <p className="text-sm font-medium text-neutral-700">No transactions in this period</p>
              <p className="mt-1 text-sm text-neutral-500">
                The balance is unchanged at <BalanceText value={data.closing} /> since{" "}
                {formatDisplayDate(data.from_date)}.
              </p>
            </div>
          ) : (
            <>
              {/* Cards on mobile */}
              <ul className="space-y-3 sm:hidden">
                {data.rows.map((row, index) => (
                  <li key={`${row.doc_no ?? row.type}-${index}`} className="rounded-xl border border-neutral-200 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className={`text-sm font-medium ${typeClass(row.type)}`}>{TXN_TYPE_LABELS[row.type]}</p>
                        <p className="text-xs text-neutral-500">
                          {formatDisplayDate(row.date)}
                          {row.doc_no ? ` · ${row.doc_no}` : ""}
                        </p>
                      </div>
                      <p className="amount shrink-0 text-right text-base font-semibold text-neutral-900">
                        {row.debit !== "0.00" ? `+${formatAmount(row.debit)}` : `−${formatAmount(row.credit)}`}
                      </p>
                    </div>
                    {row.narration && <p className="mt-1.5 text-sm text-neutral-600">{row.narration}</p>}
                    <div className="mt-2 flex items-center justify-between border-t border-neutral-100 pt-2">
                      <span className="text-xs text-neutral-500">Balance</span>
                      <BalanceText value={row.balance} className="text-sm font-medium" />
                    </div>
                  </li>
                ))}
              </ul>

              {/* Table on desktop */}
              <div className="hidden overflow-x-auto sm:block">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-neutral-300 text-left text-xs uppercase tracking-wide text-neutral-500">
                      <th scope="col" className="py-2 pr-3 font-medium">Date</th>
                      <th scope="col" className="py-2 pr-3 font-medium">Type</th>
                      <th scope="col" className="py-2 pr-3 font-medium">Document</th>
                      <th scope="col" className="py-2 pr-3 font-medium">Narration</th>
                      <th scope="col" className="py-2 pl-3 text-right font-medium">Debit</th>
                      <th scope="col" className="py-2 pl-3 text-right font-medium">Credit</th>
                      <th scope="col" className="py-2 pl-3 text-right font-medium">Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-neutral-100 bg-teal-wash/40">
                      <td className="py-2 pr-3 text-neutral-600">{formatDisplayDate(data.from_date)}</td>
                      <td className="py-2 pr-3 font-medium text-neutral-700" colSpan={3}>
                        Opening balance
                      </td>
                      <td className="py-2 pl-3" />
                      <td className="py-2 pl-3" />
                      <td className="py-2 pl-3 text-right font-medium">
                        <BalanceText value={data.opening} />
                      </td>
                    </tr>

                    {data.rows.map((row, index) => (
                      <tr key={`${row.doc_no ?? row.type}-${index}`} className="border-b border-neutral-100">
                        <td className="py-2 pr-3 whitespace-nowrap text-neutral-600">{formatDisplayDate(row.date)}</td>
                        <td className={`py-2 pr-3 whitespace-nowrap font-medium ${typeClass(row.type)}`}>
                          {TXN_TYPE_LABELS[row.type]}
                        </td>
                        <td className="py-2 pr-3 whitespace-nowrap text-neutral-600">{row.doc_no ?? "—"}</td>
                        <td className="py-2 pr-3 text-neutral-600">{row.narration ?? ""}</td>
                        <td className="amount py-2 pl-3 text-right text-neutral-900">
                          {row.debit === "0.00" ? "" : formatAmount(row.debit)}
                        </td>
                        <td className="amount py-2 pl-3 text-right text-neutral-900">
                          {row.credit === "0.00" ? "" : formatAmount(row.credit)}
                        </td>
                        <td className="py-2 pl-3 text-right">
                          <BalanceText value={row.balance} />
                        </td>
                      </tr>
                    ))}

                    <tr className="border-t-2 border-neutral-300">
                      <td className="py-2 pr-3 font-medium text-neutral-700" colSpan={4}>
                        Totals for period
                      </td>
                      <td className="amount py-2 pl-3 text-right font-semibold">{formatAmount(data.total_debit)}</td>
                      <td className="amount py-2 pl-3 text-right font-semibold">{formatAmount(data.total_credit)}</td>
                      <td className="py-2 pl-3 text-right font-semibold">
                        <BalanceText value={data.closing} />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
