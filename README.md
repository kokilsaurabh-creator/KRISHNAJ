# Krishna Jewellers — Mini ERP

Monorepo: `/backend` (FastAPI + SQLAlchemy 2.0 async + Alembic) and
`/frontend` (React 19 + Vite + TypeScript + Tailwind). Full spec:
[krishna-jewellers-erp-spec.md](krishna-jewellers-erp-spec.md).

Built so far: schema migration, the ledger service
(`backend/app/services/ledger.py`), document numbering with row-level
locking (`backend/app/services/doc_numbering.py`), auth (JWT + role
checks), parties/products CRUD, sales/purchases/payments
(create/edit/cancel), the ledger read endpoint + screen with client-side
PDF export, and entry screens for all three document types. Attachments
and the dashboard are next.

Deploys as a single Vercel project — see **Deployment** below.

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
npm run dev
```

Then open http://localhost:5173 with the backend running on port 8000
(`VITE_API_URL` overrides that if needed).

Run it from **inside** `frontend/` — Tailwind resolves its `content` globs
relative to the working directory, so starting Vite from the repo root
silently purges every utility class and the app renders unstyled.

### Theme

The palette lives in `tailwind.config.ts` as tokens — `teal`, `teal-wash`,
`peacock`, `gold`, `danger`. Components reference those names; no raw hex
belongs in a component. Red (`danger`) is reserved for cancelled documents
and payable amounts, and amounts use `tabular-nums` so ledger columns line
up.

## Deployment

One Vercel project serves both halves — no separate backend host:

```
/                       <- vercel.json: build + routing for both sides
/api/index.py           <- serverless entrypoint: mounts backend's FastAPI
                            app under /api, unmodified
/api/requirements.txt   <- runtime-only deps (no uvicorn/alembic/pytest —
                            those don't belong in a cold start)
/frontend                <- built as static output (frontend/dist)
/backend/app              <- the actual FastAPI app; bundled into the
                            function via vercel.json's includeFiles, never
                            itself aware it's running under Vercel
```

**Vercel project settings:**
- **Root Directory:** the repo root (not `/frontend` — the project now
  needs to see `/api` and `/backend` alongside it, so `vercel.json` must be
  visible at the root Vercel checks out).
- **Framework Preset:** Other (the committed `vercel.json` drives the
  build/output/routing directly; no preset needed).

**Environment variables to set in the Vercel dashboard:**

| Variable | Value | Notes |
|---|---|---|
| `VITE_API_URL` | `/api` | Relative, not a URL — frontend and API are same-origin under one Vercel domain. Build-time: Vite inlines it, so it must be set before the build runs, not added after. |
| `DATABASE_URL` | your Neon connection string, with `?sslmode=require&channel_binding=require` | Same value as `backend/.env`, entered directly in Vercel — never committed. |
| `JWT_SECRET` | a long random string | Also never committed. Generate with e.g. `openssl rand -base64 48`. |

Not needed in Vercel: `CORS_ORIGINS` (same-origin in this setup, see
`app/config.py`), `TEST_DATABASE_URL` and the `SEED_*` vars (local-only,
used for the pytest suite and for running `python -m app.seed` by hand —
neither runs as part of a deploy).

**Serverless connection handling** (`backend/app/db.py`): each Vercel
function container imports the app once at cold start and reuses that
same connection pool across every warm invocation it handles — this is
the correct, intended pattern, not something to work around. Two things
tuned specifically for it: `pool_size=1, max_overflow=2` (many containers
can exist at once, each with its own pool — SQLAlchemy's default of 5+10
multiplied across a burst of them is how you exhaust Neon's connection
limit; Neon's own pooler, already in the connection string via
`-pooler` in the hostname, absorbs the rest), and `statement_cache_size=0`
in `connect_args` (asyncpg caches prepared statements per connection,
which is incompatible with PgBouncer transaction-mode pooling under real
concurrency — a documented asyncpg/PgBouncer issue, not specific to this
app). `pool_pre_ping=True` handles a connection dying while its container
sits frozen between invocations.

**Seeding production** is a manual step, run from your own machine — it
is never part of a deploy:

```powershell
cd backend
# DATABASE_URL in .env must point at Neon, not local Postgres
.\.venv\Scripts\python.exe -m app.seed
```
