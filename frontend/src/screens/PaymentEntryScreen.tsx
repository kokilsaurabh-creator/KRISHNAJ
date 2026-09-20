import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import AttachmentPanel from "../components/AttachmentPanel";
import PartyPicker from "../components/PartyPicker";
import { ApiError, PAYMENT_MODES, api, type Bank, type Party, type Payment, type PaymentDirection } from "../lib/api";
import { formatDisplayDate } from "../lib/dates";
import { compareAmounts, formatAmount, isValidDecimal } from "../lib/money";
import { useOnlineStatus } from "../lib/useOnlineStatus";

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const DIRECTIONS: { value: PaymentDirection; label: string; hint: string }[] = [
  { value: "in", label: "Received", hint: "Money in — reduces what they owe you" },
  { value: "out", label: "Paid", hint: "Money out — reduces what you owe them" },
];

export default function PaymentEntryScreen() {
  const queryClient = useQueryClient();
  const online = useOnlineStatus();
  const [party, setParty] = useState<Party | null>(null);
  const [direction, setDirection] = useState<PaymentDirection>("in");
  const [paymentDate, setPaymentDate] = useState(todayIso);
  const [amount, setAmount] = useState("");
  const [mode, setMode] = useState<string>("Cash");
  const [referenceNo, setReferenceNo] = useState("");
  const [narration, setNarration] = useState("");
  const [transferEnabled, setTransferEnabled] = useState(false);
  const [transferParty, setTransferParty] = useState<Party | null>(null);
  const [transferAmount, setTransferAmount] = useState("");
  const [bankId, setBankId] = useState<number | null>(null);
  const [knockoffAmount, setKnockoffAmount] = useState("");
  const [knockoffReason, setKnockoffReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Payment | null>(null);

  const { data: banks } = useQuery({
    queryKey: ["banks", "active"],
    queryFn: () => api.get<Bank[]>("/banks?active=true"),
  });

  const amountValid = isValidDecimal(amount, 2) && compareAmounts(amount, "0") > 0;
  // Only a receipt from a customer can be split off to a vendor — the
  // toggle is hidden for direction "out" (see the "Received" tile below),
  // so this only matters if direction flips after it was turned on.
  const transferActive = transferEnabled && direction === "in";
  const transferAmountValid =
    isValidDecimal(transferAmount, 2) &&
    compareAmounts(transferAmount, "0") > 0 &&
    (!amountValid || compareAmounts(transferAmount, amount) <= 0);
  const transferValid = !transferActive || (transferParty !== null && transferAmountValid);
  // Bank is mandatory for a plain payment and not applicable to a
  // transfer — mirrors PaymentWrite's own validator exactly.
  const isCash = mode.trim().toLowerCase() === "cash";
  const bankValid = transferActive || isCash || bankId !== null;
  const knockoffValid =
    knockoffAmount.trim() === "" ||
    (isValidDecimal(knockoffAmount, 2) && compareAmounts(knockoffAmount, "0") >= 0);
  const canSave =
    party !== null &&
    paymentDate !== "" &&
    amountValid &&
    mode.trim() !== "" &&
    transferValid &&
    bankValid &&
    knockoffValid &&
    !saving &&
    online;

  function resetForm() {
    setParty(null);
    setDirection("in");
    setPaymentDate(todayIso());
    setAmount("");
    setMode("Cash");
    setReferenceNo("");
    setNarration("");
    setTransferEnabled(false);
    setTransferParty(null);
    setTransferAmount("");
    setBankId(null);
    setKnockoffAmount("");
    setKnockoffReason("");
    setSaved(null);
    setError(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSave || !party) return;
    setError(null);
    setSaving(true);
    try {
      const payment = await api.postJson<Payment>("/payments", {
        party_id: party.id,
        payment_date: paymentDate,
        direction,
        amount,
        mode,
        reference_no: referenceNo.trim() === "" ? null : referenceNo.trim(),
        narration: narration.trim() === "" ? null : narration.trim(),
        ...(knockoffAmount.trim() !== ""
          ? {
              knockoff_amount: knockoffAmount,
              knockoff_reason: knockoffReason.trim() === "" ? null : knockoffReason.trim(),
            }
          : {}),
        ...(transferActive && transferParty
          ? { transfer_to_party_id: transferParty.id, transfer_amount: transferAmount }
          : isCash
            ? {}
            : { bank_id: bankId }),
      });
      setSaved(payment);
      void queryClient.invalidateQueries({ queryKey: ["ledger"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the payment.");
    } finally {
      setSaving(false);
    }
  }

  if (saved) {
    return (
      <div className="space-y-5">
        <div className="rounded-xl border border-teal/30 bg-teal-wash p-4">
          <p className="text-sm font-medium text-teal">
            {saved.direction === "in" ? "Receipt saved" : "Payment saved"}
          </p>
          <p className="mt-1 text-2xl font-semibold text-neutral-900">{saved.voucher_no}</p>
          <p className="mt-0.5 text-sm text-neutral-600">
            {party?.name} · {formatDisplayDate(saved.payment_date)}
          </p>
        </div>

        <div className="rounded-xl border border-neutral-200">
          <table className="w-full text-sm">
            <tbody>
              <tr className="border-b border-neutral-100">
                <td className="px-4 py-2 text-neutral-600">Direction</td>
                <td className="px-4 py-2 text-right font-medium text-peacock">
                  {saved.direction === "in" ? "Received" : "Paid"}
                </td>
              </tr>
              <tr className="border-b border-neutral-100">
                <td className="px-4 py-2 text-neutral-600">Mode</td>
                <td className="px-4 py-2 text-right">{saved.mode}</td>
              </tr>
              {saved.reference_no && (
                <tr className="border-b border-neutral-100">
                  <td className="px-4 py-2 text-neutral-600">Reference</td>
                  <td className="px-4 py-2 text-right">{saved.reference_no}</td>
                </tr>
              )}
              {saved.bank_id && (
                <tr className="border-b border-neutral-100">
                  <td className="px-4 py-2 text-neutral-600">Bank</td>
                  <td className="px-4 py-2 text-right">
                    {banks?.find((b) => b.id === saved.bank_id)?.name ?? "—"}
                  </td>
                </tr>
              )}
              <tr className={saved.transfer_to_party_id ? "border-b border-neutral-100" : ""}>
                <td className="px-4 py-2 font-medium">Amount</td>
                <td className="amount px-4 py-2 text-right text-base font-semibold text-teal">
                  {formatAmount(saved.amount)}
                </td>
              </tr>
              {saved.knockoff_amount && (
                <tr className="border-t border-neutral-100">
                  <td className="px-4 py-2 text-neutral-600">
                    Settlement discount{saved.knockoff_reason ? ` (${saved.knockoff_reason})` : ""}
                  </td>
                  <td className="amount px-4 py-2 text-right text-peacock">{formatAmount(saved.knockoff_amount)}</td>
                </tr>
              )}
              {saved.transfer_to_party_id && saved.transfer_amount && (
                <tr>
                  <td className="px-4 py-2 text-neutral-600">Transferred to {transferParty?.name ?? "vendor"}</td>
                  <td className="amount px-4 py-2 text-right text-peacock">{formatAmount(saved.transfer_amount)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-neutral-200 p-4">
          <AttachmentPanel
            entityType="payment"
            entityId={saved.id}
            label="Screenshots"
            hint="UPI confirmation, cheque photo. Resized before upload."
          />
        </div>

        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-primary" onClick={resetForm}>
            New entry
          </button>
          <Link to="/ledger" className="btn-secondary">
            View ledger
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-neutral-900">New payment</h2>
        <p className="text-sm text-neutral-600">The voucher number is allocated when you save.</p>
      </div>

      <section className="space-y-4 rounded-xl border border-neutral-200 p-4">
        <div>
          <span className="mb-1.5 block text-sm font-medium text-neutral-700">Direction</span>
          <div className="grid grid-cols-2 gap-3">
            {DIRECTIONS.map((option) => {
              const selected = direction === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setDirection(option.value)}
                  className={`min-h-[44px] rounded-lg border px-3 py-2 text-left transition ${
                    selected
                      ? "border-teal bg-teal-wash font-medium text-teal"
                      : "border-neutral-300 bg-white text-neutral-700 hover:border-neutral-400"
                  }`}
                >
                  <span className="block text-sm">{option.label}</span>
                  <span className="block text-xs font-normal text-neutral-500">{option.hint}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-neutral-700">Party</label>
          {/* Deliberately unfiltered: a refund to a customer is money out, and
              a returned advance from a supplier is money in. */}
          <PartyPicker value={party} onChange={setParty} />
        </div>

        {direction === "in" && (
          <div className="space-y-3 rounded-lg border border-neutral-200 p-3">
            <label className="flex min-h-[36px] items-center gap-2 text-sm text-neutral-700">
              <input
                type="checkbox"
                checked={transferEnabled}
                onChange={(e) => {
                  setTransferEnabled(e.target.checked);
                  if (!e.target.checked) {
                    setTransferParty(null);
                    setTransferAmount("");
                  }
                }}
                className="h-4 w-4 rounded border-neutral-300 text-teal focus:ring-teal"
              />
              Transfer part of this to a vendor
            </label>

            {transferEnabled && (
              <div className="space-y-3">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-neutral-700">Vendor</label>
                  <PartyPicker
                    value={transferParty}
                    onChange={setTransferParty}
                    allowedTypes={["supplier", "both"]}
                    placeholder="Search vendor by name"
                  />
                </div>
                <div>
                  <label htmlFor="transfer-amount" className="mb-1.5 block text-sm font-medium text-neutral-700">
                    Transfer amount
                  </label>
                  <input
                    id="transfer-amount"
                    className="field amount text-right"
                    inputMode="decimal"
                    value={transferAmount}
                    onChange={(e) => setTransferAmount(e.target.value)}
                    placeholder="0.00"
                  />
                  {transferAmount !== "" && !transferAmountValid && (
                    <p className="mt-1 text-xs text-danger">
                      Must be more than 0 and no more than the payment amount.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {!transferActive && !isCash && (
          <div>
            <label htmlFor="payment-bank" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Bank
            </label>
            <select
              id="payment-bank"
              className="field"
              value={bankId ?? ""}
              onChange={(e) => setBankId(e.target.value === "" ? null : Number(e.target.value))}
              required
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
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="payment-date" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Date
            </label>
            <input
              id="payment-date"
              type="date"
              className="field"
              value={paymentDate}
              onChange={(e) => setPaymentDate(e.target.value)}
              required
            />
          </div>
          <div>
            <label htmlFor="payment-amount" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Amount
            </label>
            <input
              id="payment-amount"
              className="field amount text-right"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              required
            />
          </div>
        </div>

        <div>
          <span className="mb-1.5 block text-sm font-medium text-neutral-700">Mode</span>
          <div className="flex flex-wrap gap-2">
            {PAYMENT_MODES.map((option) => {
              const selected = mode === option;
              return (
                <button
                  key={option}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setMode(option)}
                  className={`min-h-[40px] rounded-full border px-4 py-1.5 text-sm transition ${
                    selected
                      ? "border-teal bg-teal-wash font-medium text-teal"
                      : "border-neutral-300 bg-white text-neutral-700 hover:border-neutral-400"
                  }`}
                >
                  {option}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label htmlFor="reference-no" className="mb-1.5 block text-sm font-medium text-neutral-700">
            Reference <span className="font-normal text-neutral-500">(UPI ref, cheque number)</span>
          </label>
          <input
            id="reference-no"
            className="field"
            value={referenceNo}
            onChange={(e) => setReferenceNo(e.target.value)}
          />
        </div>

        <div>
          <label htmlFor="payment-narration" className="mb-1.5 block text-sm font-medium text-neutral-700">
            Narration <span className="font-normal text-neutral-500">(optional)</span>
          </label>
          <input
            id="payment-narration"
            className="field"
            value={narration}
            onChange={(e) => setNarration(e.target.value)}
          />
        </div>

        <div>
          <label htmlFor="knockoff-amount" className="mb-1.5 block text-sm font-medium text-neutral-700">
            Knockoff amount <span className="font-normal text-neutral-500">(optional)</span>
          </label>
          <input
            id="knockoff-amount"
            className="field amount"
            inputMode="decimal"
            value={knockoffAmount}
            onChange={(e) => setKnockoffAmount(e.target.value)}
          />
          {!knockoffValid && <p className="mt-1 text-xs text-danger">Enter a valid amount</p>}
        </div>

        {knockoffAmount.trim() !== "" && (
          <div>
            <label htmlFor="knockoff-reason" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Reason <span className="font-normal text-neutral-500">(optional)</span>
            </label>
            <input
              id="knockoff-reason"
              className="field"
              placeholder="e.g. rounding, goodwill discount"
              value={knockoffReason}
              onChange={(e) => setKnockoffReason(e.target.value)}
            />
          </div>
        )}
      </section>

      {error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <button type="submit" className="btn-primary w-full sm:w-auto" disabled={!canSave}>
        {saving ? "Saving…" : "Save payment"}
      </button>
    </form>
  );
}
