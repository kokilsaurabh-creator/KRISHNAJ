import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import AppShell from "./components/AppShell";
import ComingSoonScreen from "./screens/ComingSoonScreen";
import HomeScreen from "./screens/HomeScreen";
import LedgerScreen from "./screens/LedgerScreen";
import LoginScreen from "./screens/LoginScreen";

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
        <Route path="sales" element={<ComingSoonScreen title="Sales" />} />
        <Route path="purchases" element={<ComingSoonScreen title="Purchase" />} />
        <Route path="payments" element={<ComingSoonScreen title="Payment" />} />
        <Route path="ledger" element={<LedgerScreen />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
