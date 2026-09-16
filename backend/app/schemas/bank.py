from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BankCreate(BaseModel):
    name: str
    account_number: str | None = None
    branch: str | None = None
    # Banks are few enough that a bulk-entry screen isn't worth building —
    # this one field at creation time covers it. amount=0 (the default)
    # simply posts no opening row.
    opening_balance: Decimal = Decimal("0")
    opening_balance_date: date


class BankUpdate(BaseModel):
    name: str | None = None
    account_number: str | None = None
    branch: str | None = None
    is_active: bool | None = None


class BankOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    account_number: str | None
    branch: str | None
    is_active: bool
    created_by: int
    created_at: datetime
