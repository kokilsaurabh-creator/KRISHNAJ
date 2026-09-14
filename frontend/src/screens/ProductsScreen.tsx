import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import { ApiError, api, type Product } from "../lib/api";
import { isValidDecimal } from "../lib/money";

type FormState = {
  code: string;
  name: string;
  category: string;
  uom: string;
  default_rate: string;
  notes: string;
  is_active: boolean;
};

function blankForm(): FormState {
  return { code: "", name: "", category: "", uom: "PCS", default_rate: "", notes: "", is_active: true };
}

function toForm(product: Product): FormState {
  return {
    code: product.code,
    name: product.name,
    category: product.category ?? "",
    uom: product.uom,
    default_rate: product.default_rate ?? "",
    notes: product.notes ?? "",
    is_active: product.is_active,
  };
}

export default function ProductsScreen() {
  const { can } = useAuth();
  const canEdit = can("edit_masters");
  const queryClient = useQueryClient();

  const [query, setQuery] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const [form, setForm] = useState<FormState>(blankForm());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = query.trim();
  const { data, isLoading } = useQuery({
    queryKey: ["products", "list", trimmed, showInactive],
    queryFn: () => {
      const params = new URLSearchParams();
      if (trimmed) params.set("q", trimmed);
      if (!showInactive) params.set("active", "true");
      return api.get<Product[]>(`/products?${params.toString()}`);
    },
  });

  const rateValid = form.default_rate.trim() === "" || isValidDecimal(form.default_rate, 2);
  const canSave = form.code.trim() !== "" && form.name.trim() !== "" && form.uom.trim() !== "" && rateValid && !saving;

  function openNew() {
    setForm(blankForm());
    setError(null);
    setEditing("new");
  }

  function openEdit(product: Product) {
    setForm(toForm(product));
    setError(null);
    setEditing(product);
  }

  function closeForm() {
    setEditing(null);
    setError(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSave) return;
    setSaving(true);
    setError(null);
    const body = {
      code: form.code.trim(),
      name: form.name.trim(),
      category: form.category.trim() || null,
      uom: form.uom.trim(),
      default_rate: form.default_rate.trim() === "" ? null : form.default_rate.trim(),
      notes: form.notes.trim() || null,
    };
    try {
      if (editing === "new") {
        await api.postJson<Product>("/products", body);
      } else if (editing) {
        await api.patchJson<Product>(`/products/${editing.id}`, { ...body, is_active: form.is_active });
      }
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      setEditing(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the product.");
    } finally {
      setSaving(false);
    }
  }

  if (editing !== null) {
    const isNew = editing === "new";
    return (
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900">{isNew ? "Add product" : "Edit product"}</h2>
          <p className="text-sm text-neutral-600">
            {isNew ? "Add an item to the catalogue." : "Update its details."}
          </p>
        </div>

        <section className="space-y-4 rounded-xl border border-neutral-200 p-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="product-code" className="mb-1.5 block text-sm font-medium text-neutral-700">
                Code
              </label>
              <input
                id="product-code"
                className="field"
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
                autoCapitalize="none"
                autoCorrect="off"
                required
                autoFocus={isNew}
              />
            </div>
            <div>
              <label htmlFor="product-uom" className="mb-1.5 block text-sm font-medium text-neutral-700">
                Unit
              </label>
              <input
                id="product-uom"
                className="field"
                value={form.uom}
                onChange={(e) => setForm((f) => ({ ...f, uom: e.target.value }))}
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="product-name" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Name
            </label>
            <input
              id="product-name"
              className="field"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="product-category" className="mb-1.5 block text-sm font-medium text-neutral-700">
                Category <span className="font-normal text-neutral-500">(optional)</span>
              </label>
              <input
                id="product-category"
                className="field"
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="product-rate" className="mb-1.5 block text-sm font-medium text-neutral-700">
                Default rate <span className="font-normal text-neutral-500">(optional)</span>
              </label>
              <input
                id="product-rate"
                className="field amount text-right"
                inputMode="decimal"
                value={form.default_rate}
                onChange={(e) => setForm((f) => ({ ...f, default_rate: e.target.value }))}
                placeholder="0.00"
              />
              {!rateValid && <p className="mt-1 text-xs text-danger">Enter a valid amount.</p>}
            </div>
          </div>

          <div>
            <label htmlFor="product-notes" className="mb-1.5 block text-sm font-medium text-neutral-700">
              Notes <span className="font-normal text-neutral-500">(optional)</span>
            </label>
            <input
              id="product-notes"
              className="field"
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </div>

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
          <button type="submit" className="btn-primary" disabled={!canSave}>
            {saving ? "Saving…" : "Save product"}
          </button>
          <button type="button" className="btn-secondary" onClick={closeForm}>
            Cancel
          </button>
        </div>
      </form>
    );
  }

  const products = data ?? [];

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900">Products</h2>
          <p className="text-sm text-neutral-600">{canEdit ? "Your catalogue." : "Your catalogue. Viewing only."}</p>
        </div>
        {canEdit && (
          <button type="button" className="btn-primary shrink-0" onClick={openNew}>
            Add product
          </button>
        )}
      </div>

      <div className="space-y-3">
        <input
          type="search"
          className="field"
          placeholder="Search by name or code"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoCapitalize="none"
          autoCorrect="off"
        />

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

      <div className="rounded-xl border border-neutral-200">
        {isLoading && <p className="px-4 py-6 text-center text-sm text-neutral-500">Loading…</p>}

        {!isLoading && products.length === 0 && (
          <p className="px-4 py-6 text-center text-sm text-neutral-500">
            {trimmed ? `No products match "${trimmed}".` : "No products yet."}
          </p>
        )}

        <ul className="divide-y divide-neutral-100">
          {products.map((product) => (
            <li key={product.id}>
              <button
                type="button"
                onClick={() => canEdit && openEdit(product)}
                disabled={!canEdit}
                className="flex w-full min-h-[56px] items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-teal-wash/40 disabled:hover:bg-transparent"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-neutral-900">
                    {product.name}
                    {!product.is_active && (
                      <span className="ml-2 text-xs font-normal text-neutral-400">Inactive</span>
                    )}
                  </p>
                  <p className="truncate text-sm text-neutral-600">
                    {[product.code, product.category, product.uom].filter(Boolean).join(" · ")}
                  </p>
                </div>
                {product.default_rate && (
                  <span className="amount shrink-0 text-sm text-neutral-700">₹{product.default_rate}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
