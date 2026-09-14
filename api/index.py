"""Vercel serverless entrypoint.

Vercel's Python runtime looks for an ASGI-compatible `app` object in this
file and serves it directly — no Lambda-style adapter (Mangum etc.) needed,
FastAPI/Starlette apps are ASGI already.

The real app lives in backend/app/main.py and stays completely unaware of
any of this: it's mounted here under /api rather than modified, so
everything already built and tested against it — the 65+ pytest tests, the
require_role dependency, local `uvicorn app.main:app` — keeps working
unprefixed and unchanged. This file exists purely so the frontend (served
from the same Vercel domain) can call the API as a same-origin relative
path.

vercel.json's `functions["api/index.py"].includeFiles` bundles backend/app/
alongside this function at deploy time, so it's present on disk here —
this just adds it to sys.path so `from app.main import app` resolves the
same top-level `app` package every other entrypoint (tests, uvicorn)
already imports.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi import FastAPI  # noqa: E402

from app.main import app as backend_app  # noqa: E402

app = FastAPI()
app.mount("/api", backend_app)
