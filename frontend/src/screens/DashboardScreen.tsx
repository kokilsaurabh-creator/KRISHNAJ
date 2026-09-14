import { IconCash, IconReceipt, IconTruckDelivery, type Icon } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";

import { api, type ActivityItem, type ActivityType, type DashboardSummary } from "../lib/api";
import { formatDisplayDate } from "../lib/dates";
import { formatCurrency } from "../lib/money";

const ACTIVITY_ICON: Record<ActivityType, { icon: Icon; tint: string }> = {
  sale: { icon: IconReceipt, tint: "bg-teal-wash text-teal" },
  purchase: { icon: IconTruckDelivery, tint: "bg-peacock/10 text-peacock" },
  payment: { icon: IconCash, tint: "bg-gold/10 text-gold" },
};

const ACTIVITY_LABEL: Record<ActivityType, string> = {
  sale: "Sale",
  purchase: "Purchase",
  payment: "Payment",
};

function ActivityRow({ item }: { item: ActivityItem }) {
  const { icon: RowIcon, tint } = ACTIVITY_ICON[item.type];
  const cancelled = item.status === "cancelled";

  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${tint}`}>
        <RowIcon size={18} stroke={1.75} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate font-medium text-neutral-900">{item.party_name}</p>
          {cancelled && (
            <span className="shrink-0 rounded-full border border-danger/30 bg-danger/5 px-2 py-0.5 text-xs font-medium text-danger">
              Cancelled
            </span>
          )}
        </div>
        <p className="truncate text-sm text-neutral-600">
          {ACTIVITY_LABEL[item.type]} · {item.doc_no} · {formatDisplayDate(item.txn_date)}
        </p>
      </div>
      <span className={`amount shrink-0 text-sm font-medium ${cancelled ? "text-neutral-400 line-through" : "text-neutral-900"}`}>
        {formatCurrency(item.amount)}
      </span>
    </li>
  );
}

export default function DashboardScreen() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary"),
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-neutral-900">Dashboard</h2>
        <p className="text-sm text-neutral-600">
          {data ? `As on ${formatDisplayDate(data.as_on_date)}` : "Outstanding and recent activity."}
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          Could not load the dashboard.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-teal px-4 py-4 text-white">
          <p className="text-xs font-medium uppercase tracking-wide text-white/75">Receivable</p>
          <p className="amount mt-1 text-xl font-semibold">
            {data ? formatCurrency(data.receivable_total) : "…"}
          </p>
        </div>
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-4">
          <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">Payable</p>
          <p className="amount mt-1 text-xl font-semibold text-neutral-800">
            {data ? formatCurrency(data.payable_total) : "…"}
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-neutral-200 px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">This month's sales</p>
        <p className="amount mt-1 text-lg font-semibold text-teal">
          {data ? formatCurrency(data.month_sales_total) : "…"}
        </p>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">Recent activity</h3>
        <div className="rounded-xl border border-neutral-200">
          {isLoading && <p className="px-4 py-6 text-center text-sm text-neutral-500">Loading…</p>}

          {!isLoading && data && data.recent_activity.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-neutral-500">No activity yet.</p>
          )}

          {data && data.recent_activity.length > 0 && (
            <ul className="divide-y divide-neutral-100">
              {data.recent_activity.map((item) => (
                <ActivityRow key={`${item.type}-${item.id}`} item={item} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
