import {
  IconBuildingBank,
  IconCash,
  IconDiamond,
  IconHash,
  IconLogout,
  IconReceipt,
  IconTruckDelivery,
  IconUsers,
  type Icon,
} from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { roleLabel, useAuth } from "../auth/AuthContext";
import { api, type ActivityItem, type ActivityType, type DashboardSummary } from "../lib/api";
import { formatDisplayDate } from "../lib/dates";
import { formatCurrencyTrim } from "../lib/money";

const RECENT_PREVIEW_COUNT = 3;

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function todayLabel(): string {
  return new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

const QUICK_ENTRY: { to: string; label: string; icon: Icon; tint: string }[] = [
  { to: "/sales/new", label: "New sale", icon: IconReceipt, tint: "bg-teal-wash text-teal" },
  { to: "/purchases/new", label: "New purchase", icon: IconTruckDelivery, tint: "bg-peacock/10 text-peacock" },
  { to: "/payments/new", label: "New payment", icon: IconCash, tint: "bg-gold/10 text-gold" },
];

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

const ACTIVITY_ROUTE: Record<ActivityType, string> = {
  sale: "sales",
  purchase: "purchases",
  payment: "payments",
};

function ActivityRow({ item }: { item: ActivityItem }) {
  const { icon: RowIcon, tint } = ACTIVITY_ICON[item.type];
  const cancelled = item.status === "cancelled";

  return (
    <li>
      <Link
        to={`/${ACTIVITY_ROUTE[item.type]}/${item.id}`}
        className="flex items-center gap-3 px-4 py-3 transition hover:bg-teal-wash/40"
      >
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
            {ACTIVITY_LABEL[item.type]} · {formatDisplayDate(item.txn_date)}
          </p>
        </div>
        <span
          className={`amount shrink-0 text-sm font-medium ${cancelled ? "text-neutral-400 line-through" : "text-neutral-900"}`}
        >
          {formatCurrencyTrim(item.amount)}
        </span>
      </Link>
    </li>
  );
}

export default function HomeScreen() {
  const { user, signOut } = useAuth();
  const [showAllActivity, setShowAllActivity] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary"),
  });

  const initial = user?.display_name?.trim().charAt(0).toUpperCase() || "?";
  const activity = data?.recent_activity ?? [];
  const visibleActivity = showAllActivity ? activity : activity.slice(0, RECENT_PREVIEW_COUNT);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 rounded-xl bg-teal px-4 py-4 text-white">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/15 text-lg font-semibold">
            {initial}
          </span>
          <div className="min-w-0">
            <p className="truncate font-semibold">
              {greeting()}
              {user ? `, ${user.display_name}` : ""}
            </p>
            <p className="truncate text-sm text-white/75">
              {user ? `${roleLabel(user.role)} · ` : ""}
              {todayLabel()}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={signOut}
          aria-label="Sign out"
          className="shrink-0 rounded-lg p-2 text-white/85 transition hover:bg-white/10"
        >
          <IconLogout size={20} />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-teal-wash px-4 py-4">
          <p className="text-sm font-medium text-teal">You'll receive</p>
          <p className="amount mt-1 text-xl font-semibold text-teal">
            {data ? formatCurrencyTrim(data.receivable_total) : "…"}
          </p>
        </div>
        <div className="rounded-xl bg-neutral-100 px-4 py-4">
          <p className="text-sm font-medium text-neutral-600">You'll pay</p>
          <p className="amount mt-1 text-xl font-semibold text-neutral-800">
            {data ? formatCurrencyTrim(data.payable_total) : "…"}
          </p>
        </div>
      </div>

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">Quick entry</h2>
        <div className="grid grid-cols-3 gap-3">
          {QUICK_ENTRY.map(({ to, label, icon: TileIcon, tint }) => (
            <Link
              key={to}
              to={to}
              className="flex flex-col items-center gap-2 rounded-xl border border-neutral-200 px-2 py-4 text-center transition hover:border-teal hover:bg-teal-wash/40"
            >
              <span className={`flex h-11 w-11 items-center justify-center rounded-full ${tint}`}>
                <TileIcon size={22} stroke={1.75} />
              </span>
              <span className="text-xs font-medium text-neutral-900">{label}</span>
            </Link>
          ))}
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Recent activity</h2>
          {activity.length > RECENT_PREVIEW_COUNT && (
            <button
              type="button"
              onClick={() => setShowAllActivity((shown) => !shown)}
              className="text-sm font-medium text-peacock underline-offset-2 hover:underline"
            >
              {showAllActivity ? "Show less" : "See all"}
            </button>
          )}
        </div>

        <div className="rounded-xl border border-neutral-200">
          {isLoading && <p className="px-4 py-6 text-center text-sm text-neutral-500">Loading…</p>}

          {!isLoading && activity.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-neutral-500">No activity yet.</p>
          )}

          {visibleActivity.length > 0 && (
            <ul className="divide-y divide-neutral-100">
              {visibleActivity.map((item) => (
                <ActivityRow key={`${item.type}-${item.id}`} item={item} />
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Link to="/parties" className="btn-secondary gap-2">
          <IconUsers size={18} stroke={1.75} />
          Parties
        </Link>
        <Link to="/products" className="btn-secondary gap-2">
          <IconDiamond size={18} stroke={1.75} />
          Products
        </Link>
        <Link to="/banks" className="btn-secondary gap-2">
          <IconBuildingBank size={18} stroke={1.75} />
          Banks
        </Link>
        {user?.role === "admin" && (
          <Link to="/settings/sales-numbering" className="btn-secondary col-span-3 gap-2">
            <IconHash size={18} stroke={1.75} />
            Sales starting number
          </Link>
        )}
      </div>
    </div>
  );
}
