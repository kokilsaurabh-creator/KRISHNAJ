import { IconBook, IconCash, IconHome, IconReceipt, IconTruckDelivery, type Icon } from "@tabler/icons-react";
import { NavLink, Outlet } from "react-router-dom";

import { useOnlineStatus } from "../lib/useOnlineStatus";
import { AppBarLogo } from "./Logo";
import InstallPrompt from "./InstallPrompt";

/** Daily-entry destinations only. Parties and Products are reached from
 * the home screen — a tab bar that needs a second row isn't a tab bar. */
const TABS: { to: string; label: string; end: boolean; icon: Icon }[] = [
  { to: "/", label: "Home", end: true, icon: IconHome },
  { to: "/sales", label: "Sales", end: false, icon: IconReceipt },
  { to: "/purchases", label: "Purchase", end: false, icon: IconTruckDelivery },
  { to: "/payments", label: "Payment", end: false, icon: IconCash },
  { to: "/ledger", label: "Ledger", end: false, icon: IconBook },
];

export default function AppShell() {
  const online = useOnlineStatus();

  return (
    <div className="flex min-h-full flex-col bg-white">
      <header className="sticky top-0 z-20 bg-teal text-white">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <AppBarLogo />

          <nav className="hidden items-center gap-1 sm:flex">
            {TABS.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm transition ${
                    isActive ? "bg-white/15 font-medium text-white" : "text-white/80 hover:bg-white/10"
                  }`
                }
              >
                {tab.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      {!online && (
        <div className="bg-danger px-4 py-2 text-center text-sm font-medium text-white">
          You're offline — changes can't be saved right now.
        </div>
      )}

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 pb-24 pt-4 sm:pb-8">
        <Outlet />
      </main>

      <InstallPrompt />

      {/* Bottom tab bar, mobile only */}
      <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-neutral-200 bg-white sm:hidden">
        <div className="flex">
          {TABS.map(({ to, label, end, icon: TabIcon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex min-h-[56px] flex-1 flex-col items-center justify-center gap-0.5 px-1 text-xs transition ${
                  isActive ? "bg-teal-wash font-medium text-teal" : "text-neutral-500"
                }`
              }
            >
              <TabIcon size={20} stroke={1.75} />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
