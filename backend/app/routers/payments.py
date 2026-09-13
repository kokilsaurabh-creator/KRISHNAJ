"""Payments: create, edit, cancel. Same transaction shape as sales.py and
purchases.py. Two payment-specific choices:

- direction ('in' = receipt, 'out' = payment) picks both the doc_sequences
  series (prefix 'RCP/' vs 'PMT/', per the spec's doc_sequences comment)
  and the ledger sign (credit vs debit) — see _txn_type_and_sign below.
- direction can't be changed on edit. voucher_no is allocated once and
  never reissued, same as a sale's invoice_no; if direction could flip
  after that, a voucher stamped 'RCP/...' could end up meaning a payment
  out, which is exactly the kind of ambiguity a challan-book habit would
  never tolerate. Cancel and re-enter instead.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db import get_session
from app.models import DocStatus, LedgerTxnType, Party, Payment, PaymentDirection, User, UserRole
from app.schemas.payment import PaymentCancelRequest, PaymentOut, PaymentWrite
from app.services import ledger
from app.services.doc_numbering import allocate_doc_number

router = APIRouter(prefix="/payments", tags=["payments"], dependencies=[Depends(get_current_user)])


def _txn_type_and_sign(direction: PaymentDirection, amount: Decimal) -> tuple[LedgerTxnType, Decimal, Decimal]:
    if direction == PaymentDirection.IN:
        return LedgerTxnType.receipt, Decimal("0"), amount  # debit, credit
    return LedgerTxnType.payment, amount, Decimal("0")


def _doc_type_and_prefix(direction: PaymentDirection) -> tuple[str, str]:
    if direction == PaymentDirection.IN:
        return "receipt", "RCP/"
    return "payment", "PMT/"


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentWrite,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Payment:
    party = await session.get(Party, body.party_id)
    if party is None or not party.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Party not found or inactive")

    doc_type, prefix = _doc_type_and_prefix(body.direction)
    voucher_no = await allocate_doc_number(session, doc_type=doc_type, txn_date=body.payment_date, prefix=prefix)

    payment = Payment(
        voucher_no=voucher_no,
        payment_date=body.payment_date,
        party_id=body.party_id,
        direction=body.direction,
        amount=body.amount,
        mode=body.mode,
        reference_no=body.reference_no,
        narration=body.narration,
        created_by=current_user.id,
    )
    session.add(payment)
    await session.flush()

    txn_type, debit, credit = _txn_type_and_sign(body.direction, body.amount)
    await ledger.post_to_ledger(
        session,
        party_id=body.party_id,
        txn_date=body.payment_date,
        txn_type=txn_type,
        source_table="payments",
        source_id=payment.id,
        doc_no=voucher_no,
        debit=debit,
        credit=credit,
        narration=body.narration,
    )

    await session.commit()
    await session.refresh(payment)
    return payment


@router.get("", response_model=list[PaymentOut])
async def list_payments(
    party_id: int | None = None,
    direction: PaymentDirection | None = None,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> list[Payment]:
    stmt = select(Payment).order_by(Payment.payment_date.desc(), Payment.id.desc())
    if party_id is not None:
        stmt = stmt.where(Payment.party_id == party_id)
    if direction is not None:
        stmt = stmt.where(Payment.direction == direction)
    if from_date is not None:
        stmt = stmt.where(Payment.payment_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(Payment.payment_date <= to_date)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{payment_id}", response_model=PaymentOut)
async def get_payment(payment_id: int, session: AsyncSession = Depends(get_session)) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    return payment


@router.patch("/{payment_id}", response_model=PaymentOut)
async def update_payment(
    payment_id: int,
    body: PaymentWrite,
    session: AsyncSession = Depends(get_session),
) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    if payment.status == DocStatus.cancelled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot edit a cancelled payment")
    if body.direction != payment.direction:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "direction cannot be changed on edit — cancel this payment and enter a new one",
        )

    party = await session.get(Party, body.party_id)
    if party is None or not party.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Party not found or inactive")

    payment.party_id = body.party_id
    payment.payment_date = body.payment_date
    payment.amount = body.amount
    payment.mode = body.mode
    payment.reference_no = body.reference_no
    payment.narration = body.narration

    txn_type, debit, credit = _txn_type_and_sign(body.direction, body.amount)
    await ledger.repost_for_source(
        session,
        source_table="payments",
        source_id=payment.id,
        party_id=body.party_id,
        txn_date=body.payment_date,
        txn_type=txn_type,
        doc_no=payment.voucher_no,
        debit=debit,
        credit=credit,
        narration=body.narration,
    )

    await session.commit()
    await session.refresh(payment)
    return payment


@router.post(
    "/{payment_id}/cancel",
    response_model=PaymentOut,
    dependencies=[Depends(require_role(UserRole.admin, UserRole.owner))],
)
async def cancel_payment(
    payment_id: int,
    body: PaymentCancelRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    if payment.status == DocStatus.cancelled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Payment is already cancelled")

    payment.status = DocStatus.cancelled
    payment.cancelled_by = current_user.id
    payment.cancelled_at = datetime.now(timezone.utc)
    payment.cancel_reason = body.reason

    await ledger.remove_for_source(session, source_table="payments", source_id=payment.id)

    await session.commit()
    await session.refresh(payment)
    return payment
