import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import AppShell from "./components/AppShell";
import BanksScreen from "./screens/BanksScreen";
import SalesNumberingScreen from "./screens/SalesNumberingScreen";
import HomeScreen from "./screens/HomeScreen";
import LoginScreen from "./screens/LoginScreen";
import PartiesScreen from "./screens/PartiesScreen";
import PaymentDetailScreen from "./screens/PaymentDetailScreen";
import PaymentEntryScreen from "./screens/PaymentEntryScreen";
import PaymentListScreen from "./screens/PaymentListScreen";
import ProductsScreen from "./screens/ProductsScreen";
import PurchaseDetailScreen from "./screens/PurchaseDetailScreen";
import PurchaseEntryScreen from "./screens/PurchaseEntryScreen";
import PurchaseListScreen from "./screens/PurchaseListScreen";
import ReportsScreen from "./screens/ReportsScreen";
import SaleDetailScreen from "./screens/SaleDetailScreen";
import SalesEntryScreen from "./screens/SalesEntryScreen";
import SalesListScreen from "./screens/SalesListScreen";

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
        {/* Dashboard was merged into Home — keep old links working. */}
        <Route path="dashboard" element={<Navigate to="/" replace />} />
        <Route path="parties" element={<PartiesScreen />} />
        <Route path="products" element={<ProductsScreen />} />
        <Route path="banks" element={<BanksScreen />} />
        <Route path="settings/sales-numbering" element={<SalesNumberingScreen />} />
        <Route path="sales" element={<SalesListScreen />} />
        <Route path="sales/new" element={<SalesEntryScreen />} />
        <Route path="sales/:id" element={<SaleDetailScreen />} />
        <Route path="purchases" element={<PurchaseListScreen />} />
        <Route path="purchases/new" element={<PurchaseEntryScreen />} />
        <Route path="purchases/:id" element={<PurchaseDetailScreen />} />
        <Route path="payments" element={<PaymentListScreen />} />
        <Route path="payments/new" element={<PaymentEntryScreen />} />
        <Route path="payments/:id" element={<PaymentDetailScreen />} />
        <Route path="ledger" element={<ReportsScreen />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
