from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import PartyType


class PartyCreate(BaseModel):
    party_type: PartyType
    name: str
    phone: str | None = None
    email: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    notes: str | None = None


class PartyUpdate(BaseModel):
    party_type: PartyType | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class PartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    party_type: PartyType
    name: str
    phone: str | None
    email: str | None
    address_line: str | None
    city: str | None
    state: str | None
    pincode: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OpeningBalanceRequest(BaseModel):
    as_of_date: date
    amount: Decimal
    narration: str | None = None


class OpeningBalanceResponse(BaseModel):
    party_id: int
    as_of_date: date
    balance: Decimal
