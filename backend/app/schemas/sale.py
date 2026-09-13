from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import DocStatus


class SaleLineIn(BaseModel):
    product_id: int
    description: str | None = None
    quantity: Decimal = Field(gt=0)
    rate: Decimal = Field(ge=0)


class SaleWrite(BaseModel):
    """Shape for both create and edit — edit is a full replace of header +
    lines, not a partial patch. See the review note on why."""

    party_id: int
    invoice_date: date
    lines: list[SaleLineIn] = Field(min_length=1)
    discount: Decimal = Decimal("0")
    narration: str | None = None


class SaleLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_no: int
    product_id: int
    description: str | None
    quantity: Decimal
    rate: Decimal
    amount: Decimal


class SaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_no: str
    invoice_date: date
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
    lines: list[SaleLineOut]


class SaleCancelRequest(BaseModel):
    reason: str = Field(min_length=1)
