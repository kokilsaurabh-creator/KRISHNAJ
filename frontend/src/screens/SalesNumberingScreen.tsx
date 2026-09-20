import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ApiError, api } from "../lib/api";

type SalesNumbering = { next_number: number; locked: boolean };

export default function SalesNumberingScreen() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["sales", "numbering"],
    queryFn: () => api.get<SalesNumbering>("/sales/numbering"),
    staleTime: 0,
  });

  if (user && user.role !== "admin") return <Navigate to="/" replace />;

  const valid = /^[1-9]\d{0,8}$/.test(value.trim());

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!valid || data?.locked) return;
    setError(null);
    setSaving(true);
    try {
      await api.putJson<SalesNumbering>("/sales/numbering", { start_number: Number(value.trim()) });
      setValue("");
      await queryClient.invalidateQueries({ queryKey: ["sales", "numbering"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the starting number.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-neutral-900">Sales starting number</h2>
        <p className="text-sm text-neutral-600">
          Invoices are plain running numbers (e.g. 867, 868, 869) that never reset.
        </p>
      </div>

      <section className="space-y-4 rounded-xl border border-neutral-200 p-4">
        <p className="text-sm text-neutral-700">
          Next invoice number: <span className="amount font-semibold">{data ? data.next_number : "…"}</span>
        </p>

        {data?.locked ? (
          <p className="rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-600">
            Locked: sales already exist, so the starting number can't be changed.
          </p>
        ) : (
          <>
            <div>
              <label htmlFor="start-number" className="mb-1.5 block text-sm font-medium text-neutral-700">
                First invoice number
              </label>
              <input
                id="start-number"
                className="field amount"
                inputMode="numeric"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
              <p className="mt-1 text-xs text-neutral-500">
                One-time setting. It locks as soon as the first sale is saved.
              </p>
            </div>
            <button type="submit" className="btn-primary" disabled={!valid || saving}>
              {saving ? "Saving…" : "Set starting number"}
            </button>
          </>
        )}

        {error && (
          <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}
      </section>
    </form>
  );
}
