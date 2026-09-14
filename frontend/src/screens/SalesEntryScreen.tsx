import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import PartyPicker from "../components/PartyPicker";
import ProductPicker from "../components/ProductPicker";
import { ApiError, api, type Party, type Product, type Sale } from "../lib/api";
import { formatDisplayDate } from "../lib/dates";
import { compareAmounts, formatAmount, isValidDecimal, lineAmount, subtractAmounts, sumAmounts } from "../lib/money";

type LineDraft = { key: number; product: Product | null; quantity: string; rate: string };

function newLine(key: number): LineDraft {
  return { key, product: null, quantity: "1", rate: "" };
}

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function SalesEntryScreen() {
  const queryClient = useQueryClient();
  const [party, setParty] = useState<Party | null>(null);
  const [invoiceDate, setInvoiceDate] = useState(todayIso);
  const [lines, setLines] = useState<LineDraft[]>([newLine(0)]);
  const [nextKey, setNextKey] = useState(1);
  const [discount, setDiscount] = useState("0");
  const [narration, setNarration] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Sale | null>(null);

  const lineAmounts = lines.map((l) => lineAmount(l.quantity, l.rate));
  const gross = sumAmounts(lineAmounts);
  const discountValid = isValidDecimal(discount, 2) && compareAmounts(discount, "0") >= 0;
  const discountWithinGross = discountValid && compareAmounts(discount, gross) <= 0;
  const net = discountWithinGross ? subtractAmounts(gross, discount) : gross;

  const linesComplete = lines.every(
    (l) => l.product !== null && isValidDecimal(l.quantity, 3) && isValidDecimal(l.rate, 2) && compareAmounts(lineAmount(l.quantity, l.rate), "0") >= 0,
  );
  const canSave = party !== null && invoiceDate !== "" && lines.length > 0 && linesComplete && discountWithinGross && !saving;

  function updateLine(key: number, patch: Partial<LineDraft>) {
    setLines((current) => current.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  }

  function resetForm() {
    setParty(null);
    setInvoiceDate(todayIso());
    setLines([newLine(nextKey)]);
    setNextKey((k) => k + 1);
    setDiscount("0");
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
      const sale = await api.postJson<Sale>("/sales", {
        party_id: party.id,
        invoice_date: invoiceDate,
        discount,
        narration: narration.trim() === "" ? null : narration.trim(),
        lines: lines.map((l) => ({
          product_id: l.product!.id,
          quantity: l.quantity,
          rate: l.rate,
        })),
      });
      setSaved(sale);
      // The ledger for this party has moved.
      void queryClient.invalidateQueries({ queryKey: ["ledger"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the invoice.");
    } finally {
      setSaving(false);
    }
  }

  if (saved) {
    return (
      <div className="space-y-5">
        <div className="rounded-xl border border-teal/30 bg-teal-wash p-4">
          <p className="text-sm font-medium text-teal">Invoice saved</p>
          <p className="mt-1 text-2xl font-semibold text-neutral-900">{saved.invoice_no}</p>
          <p className="mt-0.5 text-sm text-neutral-600">
            {party?.name} · {formatDisplayDate(saved.invoice_date)}
          </p>
        </div>

        <div className="rounded-xl border border-neutral-200">
          <table className="w-full text-sm">
            <tbody>
              {saved.lines.map((line) => (
                <tr key={line.line_no} className="border-b border-neutral-100">
                  <td className="px-4 py-2 text-neutral-600">
                    Line {line.line_no} · {line.quantity} × {formatAmount(line.rate)}
                  </td>
                  <td className="amount px-4 py-2 text-right">{formatAmount(line.amount)}</td>
                </tr>
              ))}
              <tr className="border-b border-neutral-100">
                <td className="px-4 py-2 text-neutral-600">Gross</td>
                <td className="amount px-4 py-2 text-right">{formatAmount(saved.gross_amount)}</td>
              </tr>
              <tr className="border-b border-neutral-100">
                <td className="px-4 py-2 text-neutral-600">Discount</td>
                <td className="amount px-4 py-2 text-right">{formatAmount(saved.discount)}</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-medium">Net</td>
                <td className="amount px-4 py-2 text-right text-base font-semibold text-teal">
                  {formatAmount(saved.net_amount)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-primary" onClick={resetForm}>
            New invoice
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
        <h2 className="text-lg font-semibold text-neutral-900">New sale</h2>
        <p className="text-sm text-neutral-600">The invoice number is allocated when you save.</p>
      </div>

      <section className="space-y-4 rounded-xl border border-neutral-200 p-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-neutral-700">Customer</label>
          <PartyPicker value={party} onChange={setParty} allowedTypes={["customer", "both"]} placeholder="Search customer by name" />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="invoice-date" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Invoice date
            </label>
            <input
              id="invoice-date"
              type="date"
              className="field"
              value={invoiceDate}
              onChange={(e) => setInvoiceDate(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-neutral-700">Invoice number</label>
            <p className="flex min-h-[44px] items-center rounded-lg border border-dashed border-neutral-300 px-3 text-sm text-neutral-500">
              Allocated on save
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-3 rounded-xl border border-neutral-200 p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-neutral-700">Items</h3>
          <button
            type="button"
            className="text-sm font-medium text-peacock underline-offset-2 hover:underline"
            onClick={() => {
              setLines((current) => [...current, newLine(nextKey)]);
              setNextKey((k) => k + 1);
            }}
          >
            Add line
          </button>
        </div>

        {lines.map((line, index) => (
          <div key={line.key} className="space-y-3 rounded-lg border border-neutral-200 p-3">
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-medium uppercase tracking-wide text-neutral-500">Line {index + 1}</span>
              {lines.length > 1 && (
                <button
                  type="button"
                  className="text-sm text-danger underline-offset-2 hover:underline"
                  onClick={() => setLines((current) => current.filter((l) => l.key !== line.key))}
                >
                  Remove
                </button>
              )}
            </div>

            <ProductPicker
              value={line.product}
              onChange={(product) =>
                updateLine(line.key, {
                  product,
                  rate: line.rate === "" && product?.default_rate ? product.default_rate : line.rate,
                })
              }
            />

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-neutral-600">Quantity</label>
                <input
                  className="field amount text-right"
                  inputMode="decimal"
                  value={line.quantity}
                  onChange={(e) => updateLine(line.key, { quantity: e.target.value })}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-neutral-600">Rate</label>
                <input
                  className="field amount text-right"
                  inputMode="decimal"
                  value={line.rate}
                  onChange={(e) => updateLine(line.key, { rate: e.target.value })}
                />
              </div>
              <div>
                <span className="mb-1 block text-xs font-medium text-neutral-600">Amount</span>
                <p className="amount flex min-h-[44px] items-center justify-end rounded-lg bg-neutral-50 px-3 font-medium">
                  {formatAmount(lineAmounts[index])}
                </p>
              </div>
            </div>
          </div>
        ))}
      </section>

      <section className="space-y-3 rounded-xl border border-neutral-200 p-4">
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-neutral-600">Gross</span>
          <span className="amount font-medium">{formatAmount(gross)}</span>
        </div>

        <div className="flex items-center justify-between gap-4">
          <label htmlFor="discount" className="text-sm text-neutral-600">
            Discount
          </label>
          <input
            id="discount"
            className="field amount w-40 text-right"
            inputMode="decimal"
            value={discount}
            onChange={(e) => setDiscount(e.target.value)}
          />
        </div>
        {!discountWithinGross && (
          <p className="text-right text-sm text-danger">Discount must be between 0 and the gross amount.</p>
        )}

        <div className="flex items-center justify-between gap-4 border-t border-neutral-200 pt-3">
          <span className="font-medium">Net</span>
          <span className="amount text-xl font-semibold text-teal">{formatAmount(net)}</span>
        </div>
      </section>

      <div>
        <label htmlFor="narration" className="mb-1.5 block text-sm font-medium text-neutral-700">
          Narration <span className="font-normal text-neutral-500">(optional)</span>
        </label>
        <input id="narration" className="field" value={narration} onChange={(e) => setNarration(e.target.value)} />
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <button type="submit" className="btn-primary w-full sm:w-auto" disabled={!canSave}>
        {saving ? "Saving…" : "Save invoice"}
      </button>
    </form>
  );
}
