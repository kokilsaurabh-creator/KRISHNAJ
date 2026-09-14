import {
  IconBook,
  IconCash,
  IconChevronRight,
  IconDiamond,
  IconReceipt,
  IconTruckDelivery,
  IconUsers,
  type Icon,
} from "@tabler/icons-react";
import { Link } from "react-router-dom";

import { roleLabel, useAuth } from "../auth/AuthContext";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

const QUICK_ENTRY: { to: string; label: string; icon: Icon; tint: string }[] = [
  { to: "/sales", label: "New sale", icon: IconReceipt, tint: "bg-teal-wash text-teal" },
  { to: "/purchases", label: "New purchase", icon: IconTruckDelivery, tint: "bg-peacock/10 text-peacock" },
  { to: "/payments", label: "New payment", icon: IconCash, tint: "bg-gold/10 text-gold" },
];

const RECORDS: { to: string; label: string; body: string; icon: Icon }[] = [
  { to: "/parties", label: "Parties", body: "Customers and suppliers.", icon: IconUsers },
  { to: "/products", label: "Products", body: "Your catalogue.", icon: IconDiamond },
  { to: "/ledger", label: "Ledger", body: "Statement of account, with PDF export.", icon: IconBook },
];

export default function HomeScreen() {
  const { user } = useAuth();
  const initial = user?.display_name?.trim().charAt(0).toUpperCase() || "?";

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
            {user && <p className="text-sm text-white/75">{roleLabel(user.role)}</p>}
          </div>
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
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">Records</h2>
        <div className="rounded-xl border border-neutral-200">
          <ul className="divide-y divide-neutral-100">
            {RECORDS.map(({ to, label, body, icon: RowIcon }) => (
              <li key={to}>
                <Link
                  to={to}
                  className="flex min-h-[56px] items-center gap-3 px-4 py-3 transition hover:bg-teal-wash/40"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-wash text-teal">
                    <RowIcon size={18} stroke={1.75} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-neutral-900">{label}</p>
                    <p className="truncate text-sm text-neutral-600">{body}</p>
                  </div>
                  <IconChevronRight size={18} className="shrink-0 text-neutral-400" />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
