import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { api, type Bank, type Party, type Product } from "./api";

/** id -> name for every party, active or not — a cancelled document can
 * reference a party that's since been deactivated, and it should still
 * show a name rather than a bare id. Fetched once and cached; the list
 * is small enough for a jewellery shop that this is cheaper than resolving
 * names per row server-side. */
export function usePartyMap(): Map<number, Party> {
  const { data } = useQuery({
    queryKey: ["parties", "all"],
    queryFn: () => api.get<Party[]>("/parties"),
    staleTime: 60_000,
  });
  return useMemo(() => new Map((data ?? []).map((p) => [p.id, p])), [data]);
}

export function useProductMap(): Map<number, Product> {
  const { data } = useQuery({
    queryKey: ["products", "all"],
    queryFn: () => api.get<Product[]>("/products"),
    staleTime: 60_000,
  });
  return useMemo(() => new Map((data ?? []).map((p) => [p.id, p])), [data]);
}

export function useBankMap(): Map<number, Bank> {
  const { data } = useQuery({
    queryKey: ["banks", "all"],
    queryFn: () => api.get<Bank[]>("/banks"),
    staleTime: 60_000,
  });
  return useMemo(() => new Map((data ?? []).map((b) => [b.id, b])), [data]);
}
