import { Route, Routes } from "react-router-dom";

function Placeholder() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2 p-6 text-center">
      <h1 className="text-2xl font-semibold text-maroon">Krishna Jewellers</h1>
      <p className="text-neutral-600">
        Scaffold is up. Screens land once auth and the transaction routes are built on top of the ledger service.
      </p>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<Placeholder />} />
    </Routes>
  );
}
