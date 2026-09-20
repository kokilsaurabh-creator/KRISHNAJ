import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import DateRangePicker from "../components/DateRangePicker";
import PartyPicker from "../components/PartyPicker";
import { api, type Party, type Purchase } from "../lib/api";
import { formatDisplayDate, thisMonth, type DateRange, type PresetKey } from "../lib/dates";
import { usePartyMap } from "../lib/useEntityMaps";
import { formatAmount } from "../lib/money";

export default function PurchaseListScreen() {
  const [party, setParty] = useState<Party | null>(null);
  const [preset, setPreset] = useState<PresetKey>("this_month");
  const [range, setRange] = useState<DateRange>(() => thisMonth());
  const partyMap = usePartyMap();

  const validRange = range.from !== "" && range.to !== "" && range.from <= range.to;

  const { data, isLoading } = useQuery({
    queryKey: ["purchases", "list", party?.id, range.from, range.to],
    queryFn: () => {
      const params = new URLSearchParams({ from: range.from, to: range.to });
      if (party) params.set("party_id", String(party.id));
      return api.get<Purchase[]>(`/purchases?${params.toString()}`);
    },
    enabled: validRange,
    // Shared shop: keep the list current when the app is reopened, refocused, or left open.
    staleTime: 0,
    refetchOnWindowFocus: true,
    refetchInterval: 60_000,
  });

  const purchases = data ?? [];

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900">Purchases</h2>
          <p className="text-sm text-neutral-600">Supplier bills, newest first.</p>
        </div>
        <Link to="/purchases/new" className="btn-primary shrink-0">
          + New
        </Link>
      </div>

      <section className="space-y-4 rounded-xl border border-neutral-200 p-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-neutral-700">
            Supplier <span className="font-normal text-neutral-500">(optional)</span>
          </label>
          <PartyPicker value={party} onChange={setParty} allowedTypes={["supplier", "both"]} placeholder="Search supplier by name" />
        </div>
        <div>
          <span className="mb-1.5 block text-sm font-medium text-neutral-700">Period</span>
          <DateRangePicker
            preset={preset}
            range={range}
            onChange={(nextPreset, nextRange) => {
              setPreset(nextPreset);
              setRange(nextRange);
            }}
          />
        </div>
        {!validRange && (
          <p role="alert" className="text-sm text-danger">
            The "from" date must be on or before the "to" date.
          </p>
        )}
      </section>

      <div className="rounded-xl border border-neutral-200">
        {isLoading && <p className="px-4 py-6 text-center text-sm text-neutral-500">Loading…</p>}

        {!isLoading && purchases.length === 0 && (
          <p className="px-4 py-6 text-center text-sm text-neutral-500">No purchases in this period.</p>
        )}

        <ul className="divide-y divide-neutral-100">
          {purchases.map((purchase) => {
            const cancelled = purchase.status === "cancelled";
            return (
              <li key={purchase.id}>
                <Link
                  to={`/purchases/${purchase.id}`}
                  className="flex min-h-[56px] items-center justify-between gap-3 px-4 py-3 transition hover:bg-teal-wash/40"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="truncate font-medium text-neutral-900">
                        {partyMap.get(purchase.party_id)?.name ?? `Party #${purchase.party_id}`}
                      </p>
                      {cancelled && (
                        <span className="shrink-0 rounded-full border border-danger/30 bg-danger/5 px-2 py-0.5 text-xs font-medium text-danger">
                          Cancelled
                        </span>
                      )}
                    </div>
                    <p className="truncate text-sm text-neutral-600">
                      {purchase.bill_no} · {formatDisplayDate(purchase.bill_date)}
                    </p>
                  </div>
                  <span
                    className={`amount shrink-0 text-sm font-medium ${cancelled ? "text-neutral-400 line-through" : "text-neutral-900"}`}
                  >
                    {formatAmount(purchase.net_amount)}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
