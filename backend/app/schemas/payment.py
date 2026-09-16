from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import DocStatus, PaymentDirection


class PaymentWrite(BaseModel):
    party_id: int
    payment_date: date
    direction: PaymentDirection
    amount: Decimal = Field(gt=0)
    mode: str
    reference_no: str | None = None
    narration: str | None = None

    # "Transfer part of this to a vendor" — both set together or both left
    # out. Which party it's a valid destination for (active, supplier or
    # 'both', not itself) needs a DB lookup, so that part is checked in
    # the router, not here.
    transfer_to_party_id: int | None = None
    transfer_amount: Decimal | None = Field(default=None, gt=0)

    # Which bank the money moved through. Required unless the transfer
    # above is active — a transfer is a cash hand-off, never a bank leg,
    # so bank_id must be absent there rather than silently ignored.
    # Existence/active-ness needs a DB lookup, checked in the router.
    bank_id: int | None = None

    @model_validator(mode="after")
    def _validate_transfer(self) -> Self:
        has_party = self.transfer_to_party_id is not None
        has_amount = self.transfer_amount is not None
        if has_party != has_amount:
            raise ValueError("transfer_to_party_id and transfer_amount must be set together")
        if has_amount and self.transfer_amount > self.amount:
            raise ValueError("transfer_amount cannot exceed the payment amount")
        if has_party and self.direction != PaymentDirection.IN:
            raise ValueError("a transfer can only be made from a payment received (direction 'in')")
        if has_party and self.transfer_to_party_id == self.party_id:
            raise ValueError("cannot transfer to the same party that made the payment")

        if has_party and self.bank_id is not None:
            raise ValueError("bank cannot be set when transferring part of this payment to a vendor")
        if not has_party and self.bank_id is None:
            raise ValueError("bank is required unless transferring part of this payment to a vendor")
        return self


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
    transfer_to_party_id: int | None
    transfer_amount: Decimal | None
    bank_id: int | None
    created_by: int
    cancelled_by: int | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime


class PaymentCancelRequest(BaseModel):
    reason: str = Field(min_length=1)
