from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, ledger, parties, payments, products, purchases, sales

app = FastAPI(title="Krishna Jewellers ERP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
