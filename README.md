# Krishna Jewellers — Mini ERP

Monorepo: `/backend` (FastAPI + SQLAlchemy 2.0 async + Alembic) and
`/frontend` (React 19 + Vite + TypeScript + Tailwind). Full spec:
[krishna-jewellers-erp-spec.md](krishna-jewellers-erp-spec.md).

Built so far: schema migration, the ledger service
(`backend/app/services/ledger.py`), document numbering with row-level
locking (`backend/app/services/doc_numbering.py`), auth (JWT + role
checks), parties/products CRUD, and sales (create/edit/cancel) — the first
real consumer of the ledger service. Purchases and payments are next.

## Backend setup

PowerShell (Windows) — calls the venv's `python.exe` directly so you don't
need to activate it (activation can hit an execution-policy block):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

`.env` already exists with `DATABASE_URL` filled in if you followed along
in chat — just double check it, then fill in `JWT_SECRET` and the seed
account passwords.

Run the migration against your Neon database:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Seed the 3 accounts (idempotent — safe to re-run, never overwrites an
existing user):

```powershell
.\.venv\Scripts\python.exe -m app.seed
```

Run the app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Tests

Tests need a **disposable** Postgres database — they drop and recreate
every table. Point `TEST_DATABASE_URL` in `.env` at a local Postgres
instance, not Neon: remote round trips run ~300ms each over the internet,
which turns a 43-test suite into 7 minutes; local Postgres runs the same
suite in under 10 seconds.

```powershell
.\.venv\Scripts\python.exe -m pytest
```

To run the same suite against real Neon on demand — e.g. to sanity-check
against the actual hosted Postgres version/config before a release —
override `TEST_DATABASE_URL` for just that one invocation instead of
editing `.env` (expect a couple of minutes, not seconds: this pays Neon's
network latency on every round trip):

```powershell
$env:TEST_DATABASE_URL = "<your Neon krishnaj_test connection string>"
.\.venv\Scripts\python.exe -m pytest
Remove-Item Env:\TEST_DATABASE_URL
```

macOS/Linux/bash — same idea, chain with separate lines or `&&`:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.seed
pytest
```

## Frontend setup

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Still just a placeholder screen — screens land once purchases, payments,
and the ledger view are built.
