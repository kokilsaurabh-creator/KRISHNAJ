import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import PartyPicker from "../components/PartyPicker";
import { ApiError, PAYMENT_MODES, api, type Party, type Payment, type PaymentDirection } from "../lib/api";
import { formatDisplayDate } from "../lib/dates";
import { compareAmounts, formatAmount, isValidDecimal } from "../lib/money";

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
  const [party, setParty] = useState<Party | null>(null);
  const [direction, setDirection] = useState<PaymentDirection>("in");
  const [paymentDate, setPaymentDate] = useState(todayIso);
  const [amount, setAmount] = useState("");
  const [mode, setMode] = useState<string>("Cash");
  const [referenceNo, setReferenceNo] = useState("");
  const [narration, setNarration] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Payment | null>(null);

  const amountValid = isValidDecimal(amount, 2) && compareAmounts(amount, "0") > 0;
  const canSave = party !== null && paymentDate !== "" && amountValid && mode.trim() !== "" && !saving;

  function resetForm() {
    setParty(null);
    setDirection("in");
    setPaymentDate(todayIso());
    setAmount("");
    setMode("Cash");
    setReferenceNo("");
    setNarration("");
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
              <tr>
                <td className="px-4 py-2 font-medium">Amount</td>
                <td className="amount px-4 py-2 text-right text-base font-semibold text-teal">
                  {formatAmount(saved.amount)}
                </td>
              </tr>
            </tbody>
          </table>
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
