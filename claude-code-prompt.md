# Prompt for Claude Code

Paste this as your first message, with `krishna-jewellers-erp-spec.md` in the repo root.

---

I'm building a mini ERP for my imitation jewellery business, Krishna Jewellers. The full spec is in `krishna-jewellers-erp-spec.md` at the repo root — read it first and treat every decision in it as locked. Do not propose alternatives to the stack, schema, or ledger design.

**Context:** Three users, no self-registration: `admin` (technical), `suresh` (owner), `neena` (staff). Login is by username, not email. No GST. No multi-tenancy. Sales are direct invoices, no challan stage. Purchases have free-text line items with no product master. Nothing is ever hard-deleted — documents are cancelled. I currently run this business on handwritten challan books and ledgers, so the ledger is the feature that has to be exactly right.

**Stack:** React 19 + TypeScript + Vite (PWA) frontend, FastAPI backend, Neon Postgres. Frontend deploys to Vercel. Attachments go to Vercel Blob, never base64 in the database. PDF export is client-side with pdfmake.

## Scope of this first session

Build steps 1-3 from the spec's build order and nothing else:

1. **Project scaffold** — monorepo with `/frontend` and `/backend`. Backend uses SQLAlchemy 2.0 (async) + Alembic + Pydantic v2. Frontend uses Vite, TanStack Query, React Router, and Tailwind.
2. **Schema + Alembic migration** — exactly the DDL in section 2 of the spec, no added or renamed columns.
3. **Auth and roles** — a `users` table with `username`, `password_hash`, `role` (`admin` / `owner` / `staff`). Seed three accounts from env vars with bcrypt hashes: `admin` (admin), `suresh` (owner), `neena` (staff). Seeding is idempotent — re-running must not duplicate or overwrite existing users. JWT access token; `/auth/login`, `/auth/me`, `/auth/change-password`. Every other route requires a valid token.

   Build a reusable FastAPI dependency `require_role(*roles)` and apply it per the permission matrix in section 2a of the spec. Staff calling an owner-only endpoint must get a 403 from the backend — do not rely on the UI hiding buttons.
4. **The ledger service** — this is the important part. A single module `backend/app/services/ledger.py` exposing:
   - `post_to_ledger(session, *, party_id, txn_date, txn_type, source_table, source_id, doc_no, debit, credit, narration)`
   - `repost_for_source(session, source_table, source_id, ...)` — deletes the existing row for that source and inserts the new one
   - `remove_for_source(session, source_table, source_id)`
   - `get_ledger(session, party_id, from_date, to_date)` returning opening, rows with a computed running balance, totals, and closing
   - `get_outstanding(session, party_type, as_on_date)`

   Sign convention, from the spec: sale = debit, receipt = credit, purchase = credit, payment out = debit. Balance is `SUM(debit) - SUM(credit)`; positive means receivable.

5. **Opening balance endpoint** — `POST /parties/{id}/opening-balance` writes a `ledger_entries` row with `txn_type='opening'` and no source. Idempotent: re-posting replaces the existing opening row for that party.

## Hard constraints

- No ledger writes anywhere except through `ledger.py`. Route handlers call the service; they never touch `ledger_entries` directly.
- Every document write and its ledger post happen in the **same** database transaction. If the ledger post fails, the invoice must not exist.
- Never store a running balance in the database. Compute it in the service.
- All money is `Decimal` / `NUMERIC(14,2)`. No floats anywhere, including JSON serialisation.
- The unique partial index on `(source_table, source_id)` must exist and must not be dropped — it is the guard against double-posting.
- No hard deletes on sales, purchases or payments. Cancelling sets `status='cancelled'`, records `cancelled_by`, `cancelled_at` and `cancel_reason`, and deletes the document's ledger row in the same transaction. A cancelled document cannot be edited or un-cancelled, and its number is never reused.
- Every transaction row records `created_by` from the JWT. Never accept a `created_by` value from the request body.

## Tests I want before you move on

Write pytest tests against a test database that assert:

1. A party with an opening balance, two sales, one receipt, one purchase and one payment produces `opening + SUM(debit - credit) == closing` for any date range.
2. Posting the same `(source_table, source_id)` twice raises rather than creating a duplicate ledger row.
3. Editing a sale's amount updates the ledger row rather than adding a second one.
4. Cancelling a sale removes its ledger row, keeps the sale row with `status='cancelled'`, and returns the party's closing balance to its prior value.
   4b. A cancelled sale rejects further edits and further cancellation attempts.
   4c. A staff user gets 403 on cancel, on party create, and on opening-balance; an owner gets 200 on all three.
5. A ledger range that starts after all transactions returns the correct opening and an empty rows list.

## How to work

Give me the migration and `ledger.py` first, and stop there so I can review before you build routes on top of it. Explain any judgement call you made that the spec didn't cover. If something in the spec is ambiguous or looks wrong, ask instead of guessing.
