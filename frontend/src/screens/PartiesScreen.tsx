import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import { ApiError, api, type Ledger, type Party } from "../lib/api";
import { formatBalance, isValidDecimal } from "../lib/money";

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const TYPE_FILTERS: { value: Party["party_type"] | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "customer", label: "Customers" },
  { value: "supplier", label: "Suppliers" },
  { value: "both", label: "Both" },
];

type FormState = {
  party_type: Party["party_type"];
  name: string;
  phone: string;
  email: string;
  address_line: string;
  city: string;
  state: string;
  pincode: string;
  notes: string;
  is_active: boolean;
  // Admin-only; blank means "don't touch the existing opening balance".
  opening_balance: string;
  opening_balance_date: string;
};

function blankForm(): FormState {
  return {
    party_type: "customer",
    name: "",
    phone: "",
    email: "",
    address_line: "",
    city: "",
    state: "",
    pincode: "",
    notes: "",
    is_active: true,
    opening_balance: "",
    opening_balance_date: todayIso(),
  };
}

function toForm(party: Party): FormState {
  return {
    party_type: party.party_type,
    name: party.name,
    phone: party.phone ?? "",
    email: party.email ?? "",
    address_line: party.address_line ?? "",
    city: party.city ?? "",
    state: party.state ?? "",
    pincode: party.pincode ?? "",
    notes: party.notes ?? "",
    is_active: party.is_active,
    opening_balance: "",
    opening_balance_date: todayIso(),
  };
}

export default function PartiesScreen() {
  const { can, user } = useAuth();
  // Owners may set an opening balance too; the API refuses them once the
  // party has transactions (admin only after that).
  const canSetOpening = user?.role === "admin" || user?.role === "owner";
  const canEdit = can("edit_masters");
  const queryClient = useQueryClient();

  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<Party["party_type"] | "all">("all");
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Party | "new" | null>(null);
  const [form, setForm] = useState<FormState>(blankForm());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = query.trim();
  const { data, isLoading } = useQuery({
    queryKey: ["parties", "list", trimmed, typeFilter, showInactive],
    queryFn: () => {
      const params = new URLSearchParams();
      if (trimmed) params.set("q", trimmed);
      if (typeFilter !== "all") params.set("type", typeFilter);
      if (!showInactive) params.set("active", "true");
      return api.get<Party[]>(`/parties?${params.toString()}`);
    },
  });

  const editingId = editing !== null && editing !== "new" ? editing.id : null;
  const { data: currentOpening } = useQuery({
    queryKey: ["parties", "opening", editingId],
    queryFn: async () => {
      const ledger = await api.get<Ledger>(`/ledger/${editingId}?from=1900-01-01&to=2100-12-31`);
      const row = ledger.rows.find((r) => r.type === "opening");
      if (!row) return null;
      return { amount: (Number(row.debit) - Number(row.credit)).toFixed(2), date: row.date };
    },
    enabled: canSetOpening && editingId !== null,
  });
  const openingValid = form.opening_balance.trim() === "" || isValidDecimal(form.opening_balance, 2);

  function openNew() {
    setForm(blankForm());
    setError(null);
    setEditing("new");
  }

  function openEdit(party: Party) {
    setForm(toForm(party));
    setError(null);
    setEditing(party);
  }

  function closeForm() {
    setEditing(null);
    setError(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (form.name.trim() === "" || !openingValid) return;
    setSaving(true);
    setError(null);
    const body = {
      party_type: form.party_type,
      name: form.name.trim(),
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      address_line: form.address_line.trim() || null,
      city: form.city.trim() || null,
      state: form.state.trim() || null,
      pincode: form.pincode.trim() || null,
      notes: form.notes.trim() || null,
    };
    try {
      let partyId: number;
      if (editing === "new") {
        partyId = (await api.postJson<Party>("/parties", body)).id;
      } else if (editing) {
        await api.patchJson<Party>(`/parties/${editing.id}`, { ...body, is_active: form.is_active });
        partyId = editing.id;
      } else {
        return;
      }
      // Blank = leave any existing opening balance alone; the endpoint
      // replaces rather than adds, so a zero here would wipe it.
      if (canSetOpening && form.opening_balance.trim() !== "") {
        await api.postJson(`/parties/${partyId}/opening-balance`, {
          as_of_date: form.opening_balance_date,
          amount: form.opening_balance.trim(),
        });
        void queryClient.invalidateQueries({ queryKey: ["ledger"] });
      }
      void queryClient.invalidateQueries({ queryKey: ["parties"] });
      setEditing(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the party.");
    } finally {
      setSaving(false);
    }
  }

  if (editing !== null) {
    const isNew = editing === "new";
    return (
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900">{isNew ? "Add party" : "Edit party"}</h2>
          <p className="text-sm text-neutral-600">
            {isNew ? "Add a customer or supplier." : "Update their details."}
          </p>
        </div>

        <section className="space-y-4 rounded-xl border border-neutral-200 p-4">
          <div>
            <span className="mb-1.5 block text-sm font-medium text-neutral-700">Type</span>
            <div className="grid grid-cols-3 gap-2">
              {(["customer", "supplier", "both"] as const).map((option) => {
                const selected = form.party_type === option;
                return (
                  <button
                    key={option}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setForm((f) => ({ ...f, party_type: option }))}
                    className={`min-h-[40px] rounded-lg border px-3 py-1.5 text-sm capitalize transition ${
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
            <label htmlFor="party-name" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Name
            </label>
            <input
              id="party-name"
              className="field"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
              autoFocus={isNew}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="party-phone" className="mb-1.5 block text-sm font-medium text-neutral-700">
                Phone
              </label>
              <input
                id="party-phone"
                type="tel"
                className="field"
                value={form.phone}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="party-email" className="mb-1.5 block text-sm font-medium text-neutral-700">
                Email
              </label>
              <input
                id="party-email"
                type="email"
                className="field"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </div>
          </div>

          <div>
            <label htmlFor="party-address" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Address
            </label>
            <input
              id="party-address"
              className="field"
              value={form.address_line}
              onChange={(e) => setForm((f) => ({ ...f, address_line: e.target.value }))}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="party-city" className="mb-1.5 block text-sm font-medium text-neutral-700">
                City
              </label>
              <input
                id="party-city"
                className="field"
                value={form.city}
                onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="party-state" className="mb-1.5 block text-sm font-medium text-neutral-700">
                State
              </label>
              <input
                id="party-state"
                className="field"
                value={form.state}
                onChange={(e) => setForm((f) => ({ ...f, state: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="party-pincode" className="mb-1.5 block text-sm font-medium text-neutral-700">
                Pincode
              </label>
              <input
                id="party-pincode"
                inputMode="numeric"
                className="field"
                value={form.pincode}
                onChange={(e) => setForm((f) => ({ ...f, pincode: e.target.value }))}
              />
            </div>
          </div>

          <div>
            <label htmlFor="party-notes" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Notes <span className="font-normal text-neutral-500">(optional)</span>
            </label>
            <input
              id="party-notes"
              className="field"
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </div>

          {canSetOpening && (
            <div className="space-y-3 rounded-lg border border-neutral-200 p-3">
              <p className="text-sm font-medium text-neutral-700">Opening balance</p>
              {!isNew && currentOpening && (
                <p className="text-sm text-neutral-600">
                  Currently {formatBalance(currentOpening.amount)} as on {currentOpening.date}
                </p>
              )}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="party-opening-date" className="mb-1.5 block text-sm font-medium text-neutral-700">
                    As on
                  </label>
                  <input
                    id="party-opening-date"
                    type="date"
                    className="field"
                    value={form.opening_balance_date}
                    onChange={(e) => setForm((f) => ({ ...f, opening_balance_date: e.target.value }))}
                  />
                </div>
                <div>
                  <label htmlFor="party-opening-amount" className="mb-1.5 block text-sm font-medium text-neutral-700">
                    Amount <span className="font-normal text-neutral-500">(blank = no change)</span>
                  </label>
                  <input
                    id="party-opening-amount"
                    className="field amount text-right"
                    inputMode="decimal"
                    placeholder="0.00"
                    value={form.opening_balance}
                    onChange={(e) => setForm((f) => ({ ...f, opening_balance: e.target.value }))}
                  />
                  {!openingValid && <p className="mt-1 text-xs text-danger">Enter a valid amount.</p>}
                </div>
              </div>
              <p className="text-xs text-neutral-500">Positive = they owe you. Negative = you owe them.</p>
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
          <button type="submit" className="btn-primary" disabled={saving || form.name.trim() === "" || !openingValid}>
            {saving ? "Saving…" : "Save party"}
          </button>
          <button type="button" className="btn-secondary" onClick={closeForm}>
            Cancel
          </button>
        </div>
      </form>
    );
  }

  const parties = data ?? [];

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900">Parties</h2>
          <p className="text-sm text-neutral-600">
            {canEdit ? "Customers and suppliers." : "Customers and suppliers. Viewing only."}
          </p>
        </div>
        {canEdit && (
          <button type="button" className="btn-primary shrink-0" onClick={openNew}>
            Add party
          </button>
        )}
      </div>

      <div className="space-y-3">
        <input
          type="search"
          className="field"
          placeholder="Search by name"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoCapitalize="none"
          autoCorrect="off"
        />

        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            {TYPE_FILTERS.map((option) => {
              const selected = typeFilter === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setTypeFilter(option.value)}
                  className={`min-h-[36px] rounded-full border px-3 py-1 text-sm transition ${
                    selected
                      ? "border-teal bg-teal-wash font-medium text-teal"
                      : "border-neutral-300 bg-white text-neutral-700 hover:border-neutral-400"
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
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
        </div>
      </div>

      <div className="rounded-xl border border-neutral-200">
        {isLoading && <p className="px-4 py-6 text-center text-sm text-neutral-500">Loading…</p>}

        {!isLoading && parties.length === 0 && (
          <p className="px-4 py-6 text-center text-sm text-neutral-500">
            {trimmed ? `No parties match "${trimmed}".` : "No parties yet."}
          </p>
        )}

        <ul className="divide-y divide-neutral-100">
          {parties.map((party) => (
            <li key={party.id}>
              <button
                type="button"
                onClick={() => canEdit && openEdit(party)}
                disabled={!canEdit}
                className="flex w-full min-h-[56px] items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-teal-wash/40 disabled:hover:bg-transparent"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-neutral-900">
                    {party.name}
                    {!party.is_active && <span className="ml-2 text-xs font-normal text-neutral-400">Inactive</span>}
                  </p>
                  <p className="truncate text-sm text-neutral-600">
                    {[party.party_type, party.city, party.phone].filter(Boolean).join(" · ")}
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
