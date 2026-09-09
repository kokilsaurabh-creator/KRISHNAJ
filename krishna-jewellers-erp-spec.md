# Krishna Jewellers — Mini ERP Build Spec

**Stack:** React 19 + TypeScript + Vite (PWA) · FastAPI · Neon Postgres
**Users:** three fixed accounts, username login (no email). `admin`, `suresh` (owner), `neena` (staff). No multi-tenancy, no self-registration.
**Tax:** none. Plain bills only.
**Sale flow:** direct invoice, no challan stage.
**Deletion:** nothing is hard-deleted. Documents are cancelled.

---

## 1. Locked decisions

| Decision | Choice | Why |
|---|---|---|
| Auth | Username + password, 3 seeded accounts | Only 3 people; email adds nothing without resets or notifications |
| Roles | `admin`, `owner`, `staff` — checked in backend | Staff must not edit masters or cancel documents |
| Deletion | Cancel flag, never a hard delete | Multiple people entering data; you need to see what was voided and by whom |
| Audit | `created_by` on every transaction | Answers "who entered this" without a full audit log |
| Party storage | One `parties` table with `party_type` | Ledger logic written once, works for both sides |
| Ledger | Immutable `ledger_entries`, balance always computed | No drift, no reconciliation bugs, opening/closing is one query |
| Opening balances | A `ledger_entries` row with `txn_type='opening'` | No separate table, no special-case code |
| Attachments | Object storage (Vercel Blob), URL in DB | Base64 in Postgres bloats every row ~33% and slows all reads |
| PDF export | Client-side (`pdfmake`) | Server-side PDF libs don't fit Vercel's Python bundle/cold-start budget |
| Backend hosting | Vercel Python function | Fine for single user; move to Railway/Render if cold starts annoy you |
| Offline | Read-only cache in v1 | Offline writes need a sync/conflict layer — not worth it for one user |
| Money type | `NUMERIC(14,2)`, quantity `NUMERIC(14,3)` | Never floats for money |

---

## 2. Schema (Postgres DDL)

```sql
-- ============ USERS ============

CREATE TYPE user_role AS ENUM ('admin', 'owner', 'staff');

CREATE TABLE users (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  username       TEXT        NOT NULL UNIQUE,
  display_name   TEXT        NOT NULL,
  password_hash  TEXT        NOT NULL,
  role           user_role   NOT NULL,
  is_active      BOOLEAN     NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ MASTERS ============

CREATE TYPE party_type AS ENUM ('customer', 'supplier', 'both');

CREATE TABLE parties (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  party_type    party_type   NOT NULL,
  name          TEXT         NOT NULL,
  phone         TEXT,
  email         TEXT,
  address_line  TEXT,
  city          TEXT,
  state         TEXT,
  pincode       TEXT,
  notes         TEXT,
  is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_parties_name ON parties (lower(name));
CREATE INDEX idx_parties_type ON parties (party_type) WHERE is_active;

CREATE TABLE products (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code           TEXT        NOT NULL UNIQUE,   -- your design/item code
  name           TEXT        NOT NULL,
  category       TEXT,                          -- bangles, earrings, chains...
  uom            TEXT        NOT NULL DEFAULT 'PCS',
  default_rate   NUMERIC(14,2),
  notes          TEXT,
  is_active      BOOLEAN     NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_products_name ON products (lower(name));

-- ============ ATTACHMENTS ============
-- Polymorphic: entity_type IN ('product','payment')

CREATE TABLE attachments (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entity_type  TEXT        NOT NULL,
  entity_id    BIGINT      NOT NULL,
  url          TEXT        NOT NULL,
  filename     TEXT        NOT NULL,
  mime_type    TEXT        NOT NULL,
  size_bytes   INTEGER     NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_attach_entity ON attachments (entity_type, entity_id);

-- ============ SALES ============

CREATE TYPE doc_status AS ENUM ('active', 'cancelled');

CREATE TABLE sales (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  invoice_no    TEXT        NOT NULL UNIQUE,
  invoice_date  DATE        NOT NULL,
  party_id      BIGINT      NOT NULL REFERENCES parties(id),
  gross_amount  NUMERIC(14,2) NOT NULL,   -- sum of line amounts
  discount      NUMERIC(14,2) NOT NULL DEFAULT 0,  -- net discount, header level
  net_amount    NUMERIC(14,2) NOT NULL,   -- gross - discount
  narration     TEXT,
  status        doc_status  NOT NULL DEFAULT 'active',
  created_by    BIGINT      NOT NULL REFERENCES users(id),
  cancelled_by  BIGINT      REFERENCES users(id),
  cancelled_at  TIMESTAMPTZ,
  cancel_reason TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sales_party_date ON sales (party_id, invoice_date);

CREATE TABLE sale_lines (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_id     BIGINT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  line_no     INTEGER NOT NULL,
  product_id  BIGINT NOT NULL REFERENCES products(id),
  description TEXT,                        -- optional override
  quantity    NUMERIC(14,3) NOT NULL CHECK (quantity > 0),
  rate        NUMERIC(14,2) NOT NULL CHECK (rate >= 0),
  amount      NUMERIC(14,2) NOT NULL,      -- quantity * rate
  UNIQUE (sale_id, line_no)
);

-- ============ PURCHASES ============
-- No product master: free-text item description

CREATE TABLE purchases (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  bill_no       TEXT        NOT NULL,      -- supplier's bill number
  bill_date     DATE        NOT NULL,
  party_id      BIGINT      NOT NULL REFERENCES parties(id),
  gross_amount  NUMERIC(14,2) NOT NULL,
  discount      NUMERIC(14,2) NOT NULL DEFAULT 0,
  net_amount    NUMERIC(14,2) NOT NULL,
  narration     TEXT,
  status        doc_status  NOT NULL DEFAULT 'active',
  created_by    BIGINT      NOT NULL REFERENCES users(id),
  cancelled_by  BIGINT      REFERENCES users(id),
  cancelled_at  TIMESTAMPTZ,
  cancel_reason TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (party_id, bill_no)
);
CREATE INDEX idx_purch_party_date ON purchases (party_id, bill_date);

CREATE TABLE purchase_lines (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  purchase_id       BIGINT NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
  line_no           INTEGER NOT NULL,
  item_description  TEXT NOT NULL,         -- manual entry
  uom               TEXT NOT NULL DEFAULT 'PCS',
  quantity          NUMERIC(14,3) NOT NULL CHECK (quantity > 0),
  rate              NUMERIC(14,2) NOT NULL CHECK (rate >= 0),
  amount            NUMERIC(14,2) NOT NULL,
  UNIQUE (purchase_id, line_no)
);

-- ============ PAYMENTS ============

CREATE TYPE payment_direction AS ENUM ('in', 'out');

CREATE TABLE payments (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  voucher_no    TEXT        NOT NULL UNIQUE,
  payment_date  DATE        NOT NULL,
  party_id      BIGINT      NOT NULL REFERENCES parties(id),
  direction     payment_direction NOT NULL,   -- in = receipt, out = payment
  amount        NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  mode          TEXT        NOT NULL,          -- Cash / UPI / Bank / Cheque
  reference_no  TEXT,                          -- UPI ref, cheque no
  narration     TEXT,
  status        doc_status  NOT NULL DEFAULT 'active',
  created_by    BIGINT      NOT NULL REFERENCES users(id),
  cancelled_by  BIGINT      REFERENCES users(id),
  cancelled_at  TIMESTAMPTZ,
  cancel_reason TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pay_party_date ON payments (party_id, payment_date);

-- ============ LEDGER (the core) ============

CREATE TYPE ledger_txn_type AS ENUM ('opening','sale','purchase','receipt','payment');

CREATE TABLE ledger_entries (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  party_id     BIGINT      NOT NULL REFERENCES parties(id),
  txn_date     DATE        NOT NULL,
  txn_type     ledger_txn_type NOT NULL,
  source_table TEXT,                       -- 'sales','purchases','payments', NULL for opening
  source_id    BIGINT,
  doc_no       TEXT,
  debit        NUMERIC(14,2) NOT NULL DEFAULT 0,
  credit       NUMERIC(14,2) NOT NULL DEFAULT 0,
  narration    TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (debit >= 0 AND credit >= 0),
  CHECK (NOT (debit > 0 AND credit > 0))
);
CREATE INDEX idx_ledger_party_date ON ledger_entries (party_id, txn_date, id);
CREATE UNIQUE INDEX idx_ledger_source
  ON ledger_entries (source_table, source_id)
  WHERE source_table IS NOT NULL;

-- ============ DOCUMENT NUMBERING ============

CREATE TABLE doc_sequences (
  doc_type    TEXT NOT NULL,     -- 'sale','receipt','payment'
  fy          TEXT NOT NULL,     -- '2026-27'
  prefix      TEXT NOT NULL,     -- 'KJ/', 'RCP/', 'PMT/'
  last_number INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (doc_type, fy)
);
```

### Sign convention

`balance = SUM(debit) - SUM(credit)`

| Event | Debit | Credit | Meaning |
|---|---|---|---|
| Sale to customer | net_amount | — | they owe you more |
| Receipt from customer | — | amount | they owe you less |
| Purchase from supplier | — | net_amount | you owe them more |
| Payment to supplier | amount | — | you owe them less |

**Positive balance = receivable. Negative balance = payable.** One rule, both sides.

### Ledger query

```sql
-- Opening as on :from_date
SELECT COALESCE(SUM(debit - credit), 0) AS opening
FROM ledger_entries
WHERE party_id = :pid AND txn_date < :from_date;

-- Transactions in period
SELECT txn_date, txn_type, doc_no, narration, debit, credit
FROM ledger_entries
WHERE party_id = :pid AND txn_date BETWEEN :from_date AND :to_date
ORDER BY txn_date, id;
```

Closing = opening + SUM(debit − credit) over the period. Running balance is computed in the API response, never stored.

### Write rule (non-negotiable)

Every sale/purchase/payment create, update, and cancel must write/update/delete its `ledger_entries` row **in the same database transaction**. Enforce it in one place — a `post_to_ledger(conn, doc)` service function — not scattered across route handlers. On edit: delete the old ledger row by `(source_table, source_id)` and re-insert. On cancel: set `status='cancelled'` and delete the ledger row — the document stays visible in lists and searches, its ledger effect goes to zero. The unique partial index guarantees you can never double-post.

A cancelled document can never be edited or un-cancelled, and its document number is never reused. To reverse a cancellation, raise a fresh document.

---

## 2a. Permissions

| Action | admin | owner (suresh) | staff (neena) |
|---|---|---|---|
| Create/edit sales, purchases, payments | yes | yes | yes |
| Cancel any document | yes | yes | no |
| Create/edit parties and products | yes | yes | view only |
| Set opening balances | yes | yes | no |
| View ledger and outstanding report | yes | yes | yes |
| Manage users, reset passwords | yes | yes | no |

Enforce every one of these in the FastAPI dependency layer. Hiding a button in React is a convenience, not a control — staff must get a 403 if they call the endpoint directly.

---

## 3. API surface

```
POST   /auth/login                      -> JWT (username + password)
GET    /auth/me
POST   /auth/change-password             -- own password

GET    /users                            -- admin/owner only
POST   /users                            -- admin/owner only
PATCH  /users/{id}                       -- admin/owner only (role, active, reset password)

GET    /parties?type=&q=&active=
POST   /parties
GET    /parties/{id}
PATCH  /parties/{id}
POST   /parties/{id}/opening-balance    -- writes txn_type='opening'

GET    /products?q=&active=
POST   /products
GET    /products/{id}
PATCH  /products/{id}

POST   /sales                 -- header + lines, one transaction
GET    /sales?from=&to=&party_id=
GET    /sales/{id}
PATCH  /sales/{id}
POST   /sales/{id}/cancel                -- admin/owner only, body: reason

POST   /purchases             -- same shape
GET    /purchases?...
GET    /purchases/{id}
PATCH  /purchases/{id}
POST   /purchases/{id}/cancel            -- admin/owner only

POST   /payments
GET    /payments?from=&to=&party_id=&direction=
PATCH  /payments/{id}
POST   /payments/{id}/cancel             -- admin/owner only

GET    /ledger/{party_id}?from=&to=      -- opening, rows[], closing, totals
GET    /reports/outstanding?type=customer -- all parties + closing balance as on date
GET    /dashboard/summary

POST   /attachments/upload-url            -- returns signed Vercel Blob URL
POST   /attachments                       -- record url against entity
DELETE /attachments/{id}
```

Ledger response shape:

```json
{
  "party": { "id": 12, "name": "Radha Bangles" },
  "from_date": "2026-04-01",
  "to_date": "2026-09-07",
  "opening": 45200.00,
  "rows": [
    { "date": "2026-04-12", "type": "sale", "doc_no": "KJ/2026-27/0041",
      "narration": "", "debit": 18500.00, "credit": 0, "balance": 63700.00 }
  ],
  "total_debit": 182000.00,
  "total_credit": 150000.00,
  "closing": 77200.00
}
```

---

## 4. Screens

1. **Dashboard** — total receivable, total payable, this month's sales, recent entries, quick-action buttons
2. **Parties** — list with search + balance chip, add/edit sheet
3. **Products** — list with thumbnail, add/edit with image upload
4. **Sales entry** — party picker → line items (product autocomplete, qty, rate) → net discount → total
5. **Purchase entry** — party picker → free-text lines → total
6. **Payment entry** — party, in/out toggle, amount, mode, reference, screenshot upload
7. **Ledger** — party picker + date range → opening / rows / closing → Export PDF
8. **Outstanding report** — all parties with balance as on date

---

## 5. Mobile & PWA

- `vite-plugin-pwa`, `registerType: 'autoUpdate'`, manifest with maskable icons
- Cache app shell + GET responses with `StaleWhileRevalidate`; **no offline writes in v1** — show a clear "You're offline" banner and disable save buttons
- Cancelled documents render struck-through / greyed in lists, with a "Cancelled" badge and the reason on the detail view
- Bottom tab bar on mobile: Home · Sales · Purchase · Payment · Ledger
- Entry forms as full-screen sheets, not modals
- Numeric inputs: `inputMode="decimal"`, big tap targets (min 44px), amount fields right-aligned
- Party and product pickers must be search-first — a dropdown of 300 parties is unusable on a phone
- Currency formatted Indian style (`1,23,456.00`) via `Intl.NumberFormat('en-IN')`

**Design direction:** warm and calm, not enterprise-grey. Cream/off-white background, one deep accent (maroon or deep gold works for a jewellery business), generous whitespace, one clear primary action per screen. Numbers in a tabular-figures font so columns align. Avoid dense tables on mobile — use cards with the amount as the visual anchor.

---

## 6. Build order

1. Schema + migrations + auth (3 seeded users, username login, bcrypt, JWT, role dependency)
2. Parties + Products masters with search
3. Ledger service (`post_to_ledger`) + opening balance entry
4. Sales entry → verify ledger posts correctly
5. Purchase entry
6. Payments (both directions)
7. Ledger screen + PDF export
8. Attachments (Vercel Blob)
9. Dashboard + outstanding report
10. PWA shell, icons, install prompt

Do not skip step 3. Build the ledger service before any transaction screen, and write a test that asserts: opening + period movement = closing, for a party with entries on both sides.

---

## 7. Data migration from the challan book

You don't need to key in years of history. Pick a cutover date, then for every active party enter **one opening balance row** — what they owed you (or you owed them) on that date. Everything after cutover goes in as normal entries. The old book stays as the archive.
