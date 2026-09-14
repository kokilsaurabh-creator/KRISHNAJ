export default function ComingSoonScreen({ title }: { title: string }) {
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-neutral-900">{title}</h2>
      <p className="rounded-xl border border-dashed border-neutral-300 px-4 py-10 text-center text-sm text-neutral-500">
        The {title.toLowerCase()} screen is not built yet. Its API endpoints are live and tested — the
        screen comes after the ledger.
      </p>
    </div>
  );
}
