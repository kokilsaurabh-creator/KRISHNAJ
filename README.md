# Krishna Jewellers — Mini ERP

Monorepo: `/backend` (FastAPI + SQLAlchemy 2.0 async + Alembic) and
`/frontend` (React 19 + Vite + TypeScript + Tailwind). Full spec:
[krishna-jewellers-erp-spec.md](krishna-jewellers-erp-spec.md).

This first cut delivers the schema migration and the ledger service
(`backend/app/services/ledger.py`) only — no auth, no routes yet. See the
review notes shared alongside this scaffold for the reasoning and the open
questions.

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
in chat — just double check it, then fill in `JWT_SECRET` etc. later.

Run the migration against your Neon database:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Run the ledger test suite against a **disposable** Postgres database (local
or a throwaway Neon branch — tests drop and recreate every table). Set
`TEST_DATABASE_URL` in `.env` first, then:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

macOS/Linux/bash — same idea, chain with separate lines or `&&`:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
pytest
```

## Frontend setup

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Nothing renders yet beyond a placeholder screen — there's no backend to
call against until auth and the transaction routes are built.
