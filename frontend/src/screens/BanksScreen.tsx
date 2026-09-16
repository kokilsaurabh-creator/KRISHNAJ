import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import { ApiError, api, type Bank } from "../lib/api";
import { isValidDecimal } from "../lib/money";

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

type FormState = {
  name: string;
  account_number: string;
  branch: string;
  is_active: boolean;
  // Create-time only — banks are few enough that a bulk-entry screen
  // isn't worth building, so this one field covers it.
  opening_balance: string;
  opening_balance_date: string;
};

function blankForm(): FormState {
  return {
    name: "",
    account_number: "",
    branch: "",
    is_active: true,
    opening_balance: "",
    opening_balance_date: todayIso(),
  };
}

function toForm(bank: Bank): FormState {
  return {
    name: bank.name,
    account_number: bank.account_number ?? "",
    branch: bank.branch ?? "",
    is_active: bank.is_active,
    opening_balance: "",
    opening_balance_date: todayIso(),
  };
}

export default function BanksScreen() {
  const { can } = useAuth();
  const canEdit = can("edit_masters");
  const queryClient = useQueryClient();

  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Bank | "new" | null>(null);
  const [form, setForm] = useState<FormState>(blankForm());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["banks", "list", showInactive],
    queryFn: () => {
      const params = new URLSearchParams();
      if (!showInactive) params.set("active", "true");
      return api.get<Bank[]>(`/banks?${params.toString()}`);
    },
  });

  const openingBalanceValid = form.opening_balance.trim() === "" || isValidDecimal(form.opening_balance, 2);

  function openNew() {
    setForm(blankForm());
    setError(null);
    setEditing("new");
  }

  function openEdit(bank: Bank) {
    setForm(toForm(bank));
    setError(null);
    setEditing(bank);
  }

  function closeForm() {
    setEditing(null);
    setError(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (form.name.trim() === "" || !openingBalanceValid) return;
    setSaving(true);
    setError(null);
    try {
      if (editing === "new") {
        await api.postJson<Bank>("/banks", {
          name: form.name.trim(),
          account_number: form.account_number.trim() || null,
          branch: form.branch.trim() || null,
          opening_balance: form.opening_balance.trim() || "0",
          opening_balance_date: form.opening_balance_date,
        });
      } else if (editing) {
        await api.patchJson<Bank>(`/banks/${editing.id}`, {
          name: form.name.trim(),
          account_number: form.account_number.trim() || null,
          branch: form.branch.trim() || null,
          is_active: form.is_active,
        });
      }
      void queryClient.invalidateQueries({ queryKey: ["banks"] });
      setEditing(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the bank.");
    } finally {
      setSaving(false);
    }
  }

  if (editing !== null) {
    const isNew = editing === "new";
    return (
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900">{isNew ? "Add bank" : "Edit bank"}</h2>
          <p className="text-sm text-neutral-600">{isNew ? "Add a bank account." : "Update its details."}</p>
        </div>

        <section className="space-y-4 rounded-xl border border-neutral-200 p-4">
          <div>
            <label htmlFor="bank-name" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Name
            </label>
            <input
              id="bank-name"
              className="field"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
              autoFocus={isNew}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="bank-account" className="mb-1.5 block text-sm font-medium text-neutral-700">
                Account number <span className="font-normal text-neutral-500">(optional)</span>
              </label>
              <input
                id="bank-account"
                className="field"
                value={form.account_number}
                onChange={(e) => setForm((f) => ({ ...f, account_number: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="bank-branch" className="mb-1.5 block text-sm font-medium text-neutral-700">
                Branch <span className="font-normal text-neutral-500">(optional)</span>
              </label>
              <input
                id="bank-branch"
                className="field"
                value={form.branch}
                onChange={(e) => setForm((f) => ({ ...f, branch: e.target.value }))}
              />
            </div>
          </div>

          {isNew && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="bank-opening-date" className="mb-1.5 block text-sm font-medium text-neutral-700">
                  Opening balance as on
                </label>
                <input
                  id="bank-opening-date"
                  type="date"
                  className="field"
                  value={form.opening_balance_date}
                  onChange={(e) => setForm((f) => ({ ...f, opening_balance_date: e.target.value }))}
                />
              </div>
              <div>
                <label htmlFor="bank-opening-amount" className="mb-1.5 block text-sm font-medium text-neutral-700">
                  Opening balance <span className="font-normal text-neutral-500">(optional)</span>
                </label>
                <input
                  id="bank-opening-amount"
                  className="field amount text-right"
                  inputMode="decimal"
                  placeholder="0.00"
                  value={form.opening_balance}
                  onChange={(e) => setForm((f) => ({ ...f, opening_balance: e.target.value }))}
                />
                {!openingBalanceValid && <p className="mt-1 text-xs text-danger">Enter a valid amount.</p>}
              </div>
            </div>
          )}

          {!isNew && (
            <label className="flex min-h-[44px] items-center gap-2 text-sm text-neutral-700">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                className="h-4 w-4 rounded border-neutral-300 text-teal focus:ring-teal"
              />
              Active
            </label>
          )}
        </section>

        {error && (
          <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          <button type="submit" className="btn-primary" disabled={saving || form.name.trim() === "" || !openingBalanceValid}>
            {saving ? "Saving…" : "Save bank"}
          </button>
          <button type="button" className="btn-secondary" onClick={closeForm}>
            Cancel
          </button>
        </div>
      </form>
    );
  }

  const banks = data ?? [];

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900">Banks</h2>
          <p className="text-sm text-neutral-600">{canEdit ? "Bank accounts." : "Bank accounts. Viewing only."}</p>
        </div>
        {canEdit && (
          <button type="button" className="btn-primary shrink-0" onClick={openNew}>
            Add bank
          </button>
        )}
      </div>

      <label className="flex items-center gap-1.5 text-sm text-neutral-600">
        <input
          type="checkbox"
          checked={showInactive}
          onChange={(e) => setShowInactive(e.target.checked)}
          className="h-4 w-4 rounded border-neutral-300 text-teal focus:ring-teal"
        />
        Show inactive
      </label>

      <div className="rounded-xl border border-neutral-200">
        {isLoading && <p className="px-4 py-6 text-center text-sm text-neutral-500">Loading…</p>}

        {!isLoading && banks.length === 0 && (
          <p className="px-4 py-6 text-center text-sm text-neutral-500">No banks yet.</p>
        )}

        <ul className="divide-y divide-neutral-100">
          {banks.map((bank) => (
            <li key={bank.id}>
              <button
                type="button"
                onClick={() => canEdit && openEdit(bank)}
                disabled={!canEdit}
                className="flex w-full min-h-[56px] items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-teal-wash/40 disabled:hover:bg-transparent"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-neutral-900">
                    {bank.name}
                    {!bank.is_active && <span className="ml-2 text-xs font-normal text-neutral-400">Inactive</span>}
                  </p>
                  <p className="truncate text-sm text-neutral-600">
                    {[bank.account_number, bank.branch].filter(Boolean).join(" · ")}
                  </p>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
