from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, ledger, parties, payments, products, purchases, sales

app = FastAPI(title="Krishna Jewellers ERP")


class StripApiPrefixMiddleware:
    """Strip a leading /api from the ASGI path before routing.

    In the Vercel deployment, the top-level rewrite that sends /api/* to
    this service passes the path through unmodified (Vercel's documented
    behavior — GET /api/users reaches the service as /api/users, not
    /users), so this app sees /api-prefixed paths in production. Local
    dev and the test suite hit this app directly with unprefixed paths
    (see routers' own prefixes), so this only acts when /api is present.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/api/"):
            scope = dict(scope)
            scope["path"] = scope["path"][len("/api") :] or "/"
        await self.app(scope, receive, send)


app.add_middleware(StripApiPrefixMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(parties.router)
app.include_router(products.router)
app.include_router(sales.router)
app.include_router(purchases.router)
app.include_router(payments.router)
app.include_router(ledger.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
