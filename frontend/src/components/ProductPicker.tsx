import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api, type Product } from "../lib/api";

/** Search-first, same reasoning as PartyPicker: a shop with hundreds of
 * design codes can't use a dropdown on a phone. */
export default function ProductPicker({
  value,
  onChange,
}: {
  value: Product | null;
  onChange: (product: Product | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const trimmed = query.trim();
  const { data, isFetching } = useQuery({
    queryKey: ["products", trimmed],
    queryFn: () => api.get<Product[]>(`/products?active=true&q=${encodeURIComponent(trimmed)}`),
    enabled: open && trimmed.length >= 1,
    staleTime: 30_000,
  });

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  const results = (data ?? []).slice(0, 20);

  if (value) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-lg border border-teal/30 bg-teal-wash px-3 py-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-neutral-900">{value.name}</p>
          <p className="truncate text-xs text-neutral-600">{value.code}</p>
        </div>
        <button
          type="button"
          className="shrink-0 text-sm font-medium text-peacock underline-offset-2 hover:underline"
          onClick={() => {
            onChange(null);
            setQuery("");
            setOpen(true);
          }}
        >
          Change
        </button>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        type="search"
        className="field"
        placeholder="Search product by name or code"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        autoCapitalize="none"
        autoCorrect="off"
      />

      {open && trimmed.length >= 1 && (
        <div className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-neutral-200 bg-white shadow-lg">
          {isFetching && results.length === 0 && <p className="px-3 py-3 text-sm text-neutral-500">Searching…</p>}
          {!isFetching && results.length === 0 && (
            <p className="px-3 py-3 text-sm text-neutral-500">No products match “{trimmed}”.</p>
          )}
          <ul>
            {results.map((product) => (
              <li key={product.id}>
                <button
                  type="button"
                  className="flex min-h-[44px] w-full flex-col items-start px-3 py-2 text-left hover:bg-teal-wash"
                  onClick={() => {
                    onChange(product);
                    setOpen(false);
                  }}
                >
                  <span className="text-sm font-medium text-neutral-900">{product.name}</span>
                  <span className="text-xs text-neutral-600">
                    {product.code}
                    {product.default_rate ? ` · ₹${product.default_rate}` : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
