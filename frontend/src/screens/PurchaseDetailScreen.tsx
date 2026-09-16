import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import CancelDialog from "../components/CancelDialog";
import { useAuth } from "../auth/AuthContext";
import { ApiError, api, type Purchase } from "../lib/api";
import { formatDisplayDate } from "../lib/dates";
import { usePartyMap } from "../lib/useEntityMaps";
import { formatAmount } from "../lib/money";

export default function PurchaseDetailScreen() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, can } = useAuth();
  const queryClient = useQueryClient();
  const partyMap = usePartyMap();

  const [showCancel, setShowCancel] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const { data: purchase, isLoading } = useQuery({
    queryKey: ["purchases", "detail", id],
    queryFn: () => api.get<Purchase>(`/purchases/${id}`),
  });

  async function handleCancel(reason: string) {
    setCancelling(true);
    setCancelError(null);
    try {
      await api.postJson(`/purchases/${id}/cancel`, { reason });
      setShowCancel(false);
      void queryClient.invalidateQueries({ queryKey: ["purchases"] });
      void queryClient.invalidateQueries({ queryKey: ["ledger"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    } catch (err) {
      setCancelError(err instanceof ApiError ? err.message : "Could not cancel this purchase.");
    } finally {
      setCancelling(false);
    }
  }

  if (isLoading) {
    return <p className="px-4 py-8 text-center text-sm text-neutral-500">Loading…</p>;
  }

  if (!purchase) {
    return <p className="px-4 py-8 text-center text-sm text-neutral-500">Purchase not found.</p>;
  }

  const cancelled = purchase.status === "cancelled";
  const party = partyMap.get(purchase.party_id);

  return (
    <div className="space-y-5">
      <div>
        <button type="button" onClick={() => navigate(-1)} className="text-sm text-peacock underline-offset-2 hover:underline">
          ← Back
        </button>
      </div>

      <div className={`rounded-xl border p-4 ${cancelled ? "border-neutral-200 bg-neutral-50" : "border-teal/30 bg-teal-wash"}`}>
        <div className="flex items-center gap-2">
          <p className={`text-sm font-medium ${cancelled ? "text-neutral-500" : "text-teal"}`}>Purchase</p>
          {cancelled && (
            <span className="rounded-full border border-danger/30 bg-danger/5 px-2 py-0.5 text-xs font-medium text-danger">
              Cancelled
            </span>
          )}
        </div>
        <p className={`mt-1 text-2xl font-semibold ${cancelled ? "text-neutral-500 line-through" : "text-neutral-900"}`}>
          {purchase.bill_no}
        </p>
        <p className="mt-0.5 text-sm text-neutral-600">
          {party?.name ?? `Party #${purchase.party_id}`} · {formatDisplayDate(purchase.bill_date)}
        </p>
      </div>

      <div className="rounded-xl border border-neutral-200">
        <table className="w-full text-sm">
          <tbody>
            {purchase.lines.map((line) => (
              <tr key={line.line_no} className="border-b border-neutral-100">
                <td className="px-4 py-2 text-neutral-600">
                  {line.item_description} · {line.quantity} {line.uom} × {formatAmount(line.rate)}
                </td>
                <td className="amount px-4 py-2 text-right">{formatAmount(line.amount)}</td>
              </tr>
            ))}
            <tr className="border-b border-neutral-100">
              <td className="px-4 py-2 text-neutral-600">Gross</td>
              <td className="amount px-4 py-2 text-right">{formatAmount(purchase.gross_amount)}</td>
            </tr>
            <tr className="border-b border-neutral-100">
              <td className="px-4 py-2 text-neutral-600">Discount</td>
              <td className="amount px-4 py-2 text-right">{formatAmount(purchase.discount)}</td>
            </tr>
            <tr>
              <td className="px-4 py-2 font-medium">Net</td>
              <td className="amount px-4 py-2 text-right text-base font-semibold text-teal">
                {formatAmount(purchase.net_amount)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {purchase.narration && (
        <div className="rounded-xl border border-neutral-200 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">Narration</p>
          <p className="mt-1 text-sm text-neutral-700">{purchase.narration}</p>
        </div>
      )}

      {cancelled && (
        <div className="rounded-xl border border-danger/30 bg-danger/5 p-4">
          <p className="text-sm font-medium text-danger">Cancelled</p>
          <p className="mt-1 text-sm text-neutral-700">
            By {purchase.cancelled_by === user?.id ? "you" : `user #${purchase.cancelled_by}`}
            {purchase.cancelled_at ? ` on ${formatDisplayDate(purchase.cancelled_at.slice(0, 10))}` : ""}
          </p>
          {purchase.cancel_reason && <p className="mt-1 text-sm text-neutral-700">Reason: {purchase.cancel_reason}</p>}
        </div>
      )}

      {cancelError && !showCancel && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {cancelError}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <Link to="/ledger" className="btn-secondary">
          View ledger
        </Link>
        {!cancelled && can("cancel_documents") && (
          <button
            type="button"
            className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-danger px-4 py-2 font-medium text-danger transition hover:bg-danger/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-danger/30"
            onClick={() => setShowCancel(true)}
          >
            Cancel purchase
          </button>
        )}
      </div>

      {showCancel && (
        <CancelDialog
          busy={cancelling}
          error={cancelError}
          onConfirm={handleCancel}
          onDismiss={() => {
            setShowCancel(false);
            setCancelError(null);
          }}
        />
      )}
    </div>
  );
}
