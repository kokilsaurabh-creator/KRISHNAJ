from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.models import LedgerTxnType


class CashLedgerRowOut(BaseModel):
    date: date
    type: LedgerTxnType
    doc_no: str | None
    narration: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal
    party_name: str | None


class CashLedgerOut(BaseModel):
    from_date: date
    to_date: date
    opening: Decimal
    rows: list[CashLedgerRowOut]
    total_debit: Decimal
    total_credit: Decimal
    closing: Decimal


class CashOpeningBalanceRequest(BaseModel):
    as_of_date: date
    amount: Decimal


class CashOpeningBalanceOut(BaseModel):
    """amount/as_of_date are None until an admin has set the balance once."""

    amount: Decimal | None
    as_of_date: date | None
