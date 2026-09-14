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

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {[
          { to: "/sales", title: "New sale", body: "Invoice a customer. The number is allocated on save." },
          { to: "/purchases", title: "New purchase", body: "Record a supplier's bill against their own number." },
          { to: "/payments", title: "New payment", body: "Money received from, or paid to, a party." },
          { to: "/ledger", title: "Ledger", body: "Statement of account for a party, with PDF export." },
        ].map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="block rounded-xl border border-neutral-200 p-4 transition hover:border-teal hover:bg-teal-wash/40"
          >
            <p className="font-medium text-neutral-900">{card.title}</p>
            <p className="mt-0.5 text-sm text-neutral-600">{card.body}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
