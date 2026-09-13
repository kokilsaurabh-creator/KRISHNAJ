from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import DocStatus


class PurchaseLineIn(BaseModel):
    item_description: str
    uom: str = "PCS"
    quantity: Decimal = Field(gt=0)
    rate: Decimal = Field(ge=0)


class PurchaseWrite(BaseModel):
    """Shape for both create and edit — same full-replace reasoning as
    SaleWrite."""

    party_id: int
    bill_no: str
    bill_date: date
    lines: list[PurchaseLineIn] = Field(min_length=1)
    discount: Decimal = Decimal("0")
    narration: str | None = None


class PurchaseLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_no: int
    item_description: str
    uom: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_no: str
    bill_date: date
    party_id: int
    gross_amount: Decimal
    discount: Decimal
    net_amount: Decimal
    narration: str | None
    status: DocStatus
    created_by: int
    cancelled_by: int | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime
    lines: list[PurchaseLineOut]


class PurchaseCancelRequest(BaseModel):
    reason: str = Field(min_length=1)
