import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import AppShell from "./components/AppShell";
import DashboardScreen from "./screens/DashboardScreen";
import HomeScreen from "./screens/HomeScreen";
import LedgerScreen from "./screens/LedgerScreen";
import LoginScreen from "./screens/LoginScreen";
import PartiesScreen from "./screens/PartiesScreen";
import PaymentEntryScreen from "./screens/PaymentEntryScreen";
import ProductsScreen from "./screens/ProductsScreen";
import PurchaseEntryScreen from "./screens/PurchaseEntryScreen";
import SalesEntryScreen from "./screens/SalesEntryScreen";

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-full items-center justify-center bg-white">
        <p className="text-sm text-neutral-500">Loading…</p>
      </div>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="*" element={<LoginScreen />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomeScreen />} />
        <Route path="dashboard" element={<DashboardScreen />} />
        <Route path="parties" element={<PartiesScreen />} />
        <Route path="products" element={<ProductsScreen />} />
        <Route path="sales" element={<SalesEntryScreen />} />
        <Route path="purchases" element={<PurchaseEntryScreen />} />
        <Route path="payments" element={<PaymentEntryScreen />} />
        <Route path="ledger" element={<LedgerScreen />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
