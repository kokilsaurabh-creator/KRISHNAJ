from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import LedgerTxnType


class LedgerPartyOut(BaseModel):
    """Party identity for the ledger header. Carries the address fields
    too — the client-side PDF export prints them, and fetching them here
    saves the ledger screen a second round trip."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str | None
    address_line: str | None
    city: str | None
    state: str | None
    pincode: str | None


class LedgerRowOut(BaseModel):
    date: date
    type: LedgerTxnType
    doc_no: str | None
    narration: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal


class LedgerOut(BaseModel):
    party: LedgerPartyOut
    from_date: date
    to_date: date
    opening: Decimal
    rows: list[LedgerRowOut]
    total_debit: Decimal
    total_credit: Decimal
    closing: Decimal
