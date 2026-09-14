import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api, type Party } from "../lib/api";

/**
 * Search-first party selection. Deliberately not a <select>: with a few
 * hundred parties a dropdown is unusable on a phone, so nothing is listed
 * until something is typed, and results are capped to a readable number.
 */
export default function PartyPicker({
  value,
  onChange,
  allowedTypes,
  placeholder = "Search party by name",
}: {
  value: Party | null;
  onChange: (party: Party | null) => void;
  /** Restricts which parties can be chosen. A 'both' party belongs on
   * either side, so pass it alongside the side you want — filtering is
   * done here rather than via the API's exact-match `type` filter, which
   * would drop 'both' parties from the list. */
  allowedTypes?: Party["party_type"][];
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const trimmed = query.trim();
  const { data, isFetching } = useQuery({
    queryKey: ["parties", trimmed],
    queryFn: () => api.get<Party[]>(`/parties?active=true&q=${encodeURIComponent(trimmed)}`),
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

  const results = (data ?? [])
    .filter((p) => !allowedTypes || allowedTypes.includes(p.party_type))
    .slice(0, 20);

  if (value) {
    return (
      <div className="rounded-lg border border-teal/30 bg-teal-wash px-3 py-2.5">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-medium text-neutral-900">{value.name}</p>
            {(value.city || value.phone) && (
              <p className="truncate text-sm text-neutral-600">
                {[value.city, value.phone].filter(Boolean).join(" · ")}
              </p>
            )}
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
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        type="search"
        className="field"
        placeholder={placeholder}
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
        <div className="absolute z-10 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-neutral-200 bg-white shadow-lg">
          {isFetching && results.length === 0 && (
            <p className="px-3 py-3 text-sm text-neutral-500">Searching…</p>
          )}

          {!isFetching && results.length === 0 && (
            <p className="px-3 py-3 text-sm text-neutral-500">No parties match “{trimmed}”.</p>
          )}

          <ul>
            {results.map((party) => (
              <li key={party.id}>
                <button
                  type="button"
                  className="flex min-h-[44px] w-full flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-teal-wash"
                  onClick={() => {
                    onChange(party);
                    setOpen(false);
                  }}
                >
                  <span className="font-medium text-neutral-900">{party.name}</span>
                  {(party.city || party.phone) && (
                    <span className="text-sm text-neutral-600">
                      {[party.city, party.phone].filter(Boolean).join(" · ")}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
