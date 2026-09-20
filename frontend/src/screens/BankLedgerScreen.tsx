import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import DateRangePicker from "../components/DateRangePicker";
import { api, TXN_TYPE_LABELS, type Bank, type BankLedger, type BankLedgerRow } from "../lib/api";
import { downloadBankLedgerPdf } from "../lib/bankLedgerPdf";
import { formatDisplayDate, thisFY, type DateRange, type PresetKey } from "../lib/dates";
import { absoluteAmount, balanceMarker, formatAmount, isNegative } from "../lib/money";

/** Same visual language as the party ledger's BalanceText/SummaryFigure —
 * not shared code, since importing screen-local helpers across files
 * would couple two pages that the task deliberately keeps independent
 * ("Party Ledger — unchanged"). */
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

function typeClass(type: BankLedgerRow["type"]): string {
  return type === "receipt" || type === "payment" ? "text-peacock" : "text-neutral-700";
}

export default function BankLedgerScreen() {
  const [bankId, setBankId] = useState<number | null>(null);
  const [preset, setPreset] = useState<PresetKey>("this_fy");
  const [range, setRange] = useState<DateRange>(() => thisFY());
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const { data: banks } = useQuery({
    queryKey: ["banks", "active"],
    queryFn: () => api.get<Bank[]>("/banks?active=true"),
  });

  const validRange = range.from !== "" && range.to !== "" && range.from <= range.to;

  // Filters are only a draft until "Go"; each tap uses a new nonce and
  // gcTime 0 so it always fetches fresh from the backend.
  const [run, setRun] = useState<{ bankId: number; range: DateRange; nonce: number } | null>(null);

  const { data, isPending, isFetching, isError, error } = useQuery({
    queryKey: ["bank-ledger", run?.bankId, run?.range.from, run?.range.to, run?.nonce],
    queryFn: () => api.get<BankLedger>(`/bank-ledger/${run!.bankId}?from=${run!.range.from}&to=${run!.range.to}`),
    enabled: run !== null,
    gcTime: 0,
    staleTime: 0,
  });

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-neutral-900">Bank ledger</h2>
        <p className="text-sm text-neutral-600">Statement for one bank account over a period.</p>
      </div>

      <section className="space-y-4 rounded-xl border border-neutral-200 p-4">
        <div>
          <label htmlFor="bank-select" className="mb-1.5 block text-sm font-medium text-neutral-700">
            Bank
          </label>
          <select
            id="bank-select"
            className="field"
            value={bankId ?? ""}
            onChange={(e) => setBankId(e.target.value === "" ? null : Number(e.target.value))}
          >
            <option value="">Select a bank</option>
            {(banks ?? []).map((bank) => (
              <option key={bank.id} value={bank.id}>
                {bank.name}
                {bank.account_number ? ` · ${bank.account_number}` : ""}
              </option>
            ))}
          </select>
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

        <button
          type="button"
          className="btn-primary w-full sm:w-auto"
          disabled={bankId === null || !validRange || isFetching}
          onClick={() => bankId !== null && setRun({ bankId, range, nonce: Date.now() })}
        >
          {isFetching ? "Loading…" : "Go"}
        </button>

        {!validRange && (
          <p role="alert" className="text-sm text-danger">
            The "from" date must be on or before the "to" date.
          </p>
        )}
      </section>

      {run === null && (
        <p className="rounded-xl border border-dashed border-neutral-300 px-4 py-8 text-center text-sm text-neutral-500">
          Pick a bank and period above, then tap Go.
        </p>
      )}

      {run !== null && isPending && (
        <p className="px-4 py-8 text-center text-sm text-neutral-500">Loading ledger…</p>
      )}

      {isError && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {error instanceof Error ? error.message : "Could not load the bank ledger."}
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
                  await downloadBankLedgerPdf(data);
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
                        {row.party_name && <p className="text-xs text-neutral-600">{row.party_name}</p>}
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
                        <td className="py-2 pr-3 whitespace-nowrap text-neutral-600">
                          {row.doc_no ?? "—"}
                          {row.party_name && <span className="block text-xs text-neutral-500">{row.party_name}</span>}
                        </td>
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
