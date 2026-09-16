import { useState } from "react";

/** Confirm-with-reason prompt for cancelling a document. cancel_reason is
 * a required column, so the reason is required here too — there's no
 * server-side default to fall back on. */
export default function CancelDialog({
  busy,
  error,
  onConfirm,
  onDismiss,
}: {
  busy: boolean;
  error: string | null;
  onConfirm: (reason: string) => void;
  onDismiss: () => void;
}) {
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center" role="dialog" aria-modal="true">
      <div className="w-full max-w-sm rounded-t-2xl bg-white p-5 sm:rounded-2xl">
        <h3 className="text-base font-semibold text-neutral-900">Cancel this document?</h3>
        <p className="mt-1 text-sm text-neutral-600">
          This removes it from the ledger. The document itself stays on record, marked cancelled.
        </p>

        <label htmlFor="cancel-reason" className="mb-1.5 mt-4 block text-sm font-medium text-neutral-700">
          Reason
        </label>
        <textarea
          id="cancel-reason"
          className="field min-h-[80px]"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          autoFocus
          required
        />

        {error && (
          <p role="alert" className="mt-3 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            className="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-danger px-4 py-2 font-medium text-white transition hover:bg-danger/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-danger/40 disabled:opacity-50"
            disabled={busy || trimmed === ""}
            onClick={() => onConfirm(trimmed)}
          >
            {busy ? "Cancelling…" : "Cancel document"}
          </button>
          <button type="button" className="btn-secondary" onClick={onDismiss} disabled={busy}>
            Never mind
          </button>
        </div>
      </div>
    </div>
  );
}
