from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import DocStatus, PaymentDirection


class PaymentWrite(BaseModel):
    party_id: int
    payment_date: date
    direction: PaymentDirection
    amount: Decimal = Field(gt=0)
    mode: str
    reference_no: str | None = None
    narration: str | None = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    voucher_no: str
    payment_date: date
    party_id: int
    direction: PaymentDirection
    amount: Decimal
    mode: str
    reference_no: str | None
    narration: str | None
    status: DocStatus
    created_by: int
    cancelled_by: int | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime


class PaymentCancelRequest(BaseModel):
    reason: str = Field(min_length=1)
