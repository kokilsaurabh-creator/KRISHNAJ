from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import LedgerTxnType


class BankLedgerBankOut(BaseModel):
    """Bank identity for the ledger header — mirrors LedgerPartyOut's role
    for the party ledger."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    account_number: str | None
    branch: str | None


class BankLedgerRowOut(BaseModel):
    date: date
    type: LedgerTxnType
    doc_no: str | None
    narration: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal


class BankLedgerOut(BaseModel):
    bank: BankLedgerBankOut
    from_date: date
    to_date: date
    opening: Decimal
    rows: list[BankLedgerRowOut]
    total_debit: Decimal
    total_credit: Decimal
    closing: Decimal
