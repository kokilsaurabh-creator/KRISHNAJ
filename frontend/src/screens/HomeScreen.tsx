import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function HomeScreen() {
  const { user, can } = useAuth();

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-neutral-900">
          Welcome{user ? `, ${user.display_name}` : ""}
        </h2>
        <p className="text-sm text-neutral-600">
          {can("cancel_documents")
            ? "You can enter, edit and cancel documents."
            : "You can enter and edit documents. Cancelling is restricted to the owner."}
        </p>
      </div>

      <Link
        to="/ledger"
        className="block rounded-xl border border-neutral-200 p-4 transition hover:border-teal hover:bg-teal-wash/40"
      >
        <p className="font-medium text-neutral-900">Ledger</p>
        <p className="mt-0.5 text-sm text-neutral-600">
          Statement of account for a party, with PDF export.
        </p>
      </Link>

      <p className="rounded-xl border border-dashed border-neutral-300 px-4 py-6 text-center text-sm text-neutral-500">
        Sales, purchase and payment screens are next. The ledger is live now.
      </p>
    </div>
  );
}
