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

"Transfer part of this to a vendor" (customer payments only): one payment
row, two ledger rows sharing that row's id as source_id but under
different source_table values — 'payments' for the receipt from the
customer (full amount, as always) and 'payment_transfer' for the debit to
the vendor (transfer amount only). The unique index on
(source_table, source_id) is per-table, so this doesn't collide with the
guarantee it gives every other document; it's what lets one payment have
exactly two ledger rows instead of one. See PaymentWrite for the
same-payment-amount / active-supplier-or-both validation.

Bank tracking: a third, independent leg, in a different table again
(bank_ledger_entries, not ledger_entries) — so it reuses source_table
'payments' rather than needing its own distinct value; that table's own
unique index on (source_table, source_id) is what stops a payment
posting to a bank twice, same mechanism as everywhere else, just scoped
to bank_ledger_entries instead of ledger_entries. Mutually exclusive
with the transfer above: bank_id is required unless transferring, and
must be absent when transferring (PaymentWrite enforces the shape;
_load_bank enforces the bank itself is real and active).
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db import get_session
from app.models import Bank, DocStatus, LedgerTxnType, Party, PartyType, Payment, PaymentDirection, User, UserRole
from app.schemas.payment import PaymentCancelRequest, PaymentOut, PaymentWrite
from app.services import bank_ledger, cash_ledger, ledger
from app.services.doc_numbering import allocate_doc_number

router = APIRouter(prefix="/payments", tags=["payments"], dependencies=[Depends(get_current_user)])

TRANSFER_SOURCE_TABLE = "payment_transfer"
KNOCKOFF_SOURCE_TABLE = "payment_knockoff"


def _txn_type_and_sign(direction: PaymentDirection, amount: Decimal) -> tuple[LedgerTxnType, Decimal, Decimal]:
    if direction == PaymentDirection.IN:
        return LedgerTxnType.receipt, Decimal("0"), amount  # debit, credit
    return LedgerTxnType.payment, amount, Decimal("0")


def _bank_txn_type_and_sign(direction: PaymentDirection, amount: Decimal) -> tuple[LedgerTxnType, Decimal, Decimal]:
    """The bank leg's sign is the OPPOSITE pair from _txn_type_and_sign,
    not the same one: a receipt credits the party (reduces what they owe)
    but debits the bank (money deposited in); a payment out debits the
    party but credits the bank (money withdrawn). Kept as its own
    function rather than reusing the party leg's debit/credit values, so
    that relationship can't accidentally get re-collapsed into "just pass
    the same numbers through" again.
    """
    if direction == PaymentDirection.IN:
        return LedgerTxnType.receipt, amount, Decimal("0")  # deposit: debit
    return LedgerTxnType.payment, Decimal("0"), amount  # withdrawal: credit


def _doc_type_and_prefix(direction: PaymentDirection) -> tuple[str, str]:
    if direction == PaymentDirection.IN:
        return "receipt", "RCP/"
    return "payment", "PMT/"


async def _load_transfer_target(session: AsyncSession, transfer_to_party_id: int) -> Party:
    vendor = await session.get(Party, transfer_to_party_id)
    if vendor is None or not vendor.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Transfer party not found or inactive")
    if vendor.party_type not in (PartyType.supplier, PartyType.both):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Transfer party must be a supplier")
    return vendor


async def _load_bank(session: AsyncSession, bank_id: int) -> Bank:
    bank = await session.get(Bank, bank_id)
    if bank is None or not bank.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bank not found or inactive")
    return bank


async def _check_knockoff(
    session: AsyncSession,
    *,
    party_id: int,
    direction: PaymentDirection,
    knockoff: Decimal,
    exclude_payment_id: int | None,
) -> None:
    """A knockoff writes off part of what's owed, so it can't exceed what
    is owed: the party's balance as it stood before this payment (for an
    edit, with the payment's own legs taken out first). Receivable for a
    receipt, payable for a payment out.
    """
    balance = await ledger.get_party_balance(session, party_id, exclude_payment_id=exclude_payment_id)
    outstanding = balance if direction == PaymentDirection.IN else -balance
    if knockoff > outstanding:
        shown = max(outstanding, Decimal("0.00"))
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Knockoff can't exceed the outstanding balance (Rs {shown:,.2f})",
        )


async def _post_knockoff_leg(
    session: AsyncSession,
    *,
    payment_id: int,
    party_id: int,
    direction: PaymentDirection,
    knockoff: Decimal,
    payment_date: date,
    voucher_no: str,
    reason: str | None,
) -> None:
    """Post (or replace) the settlement-discount line on the SAME party,
    on the same side as the payment itself: a knockoff on a receipt is a
    credit, on a payment out a debit. The bank ledger is deliberately not
    involved — no money moved for this portion.
    """
    _, debit, credit = _txn_type_and_sign(direction, knockoff)
    await ledger.repost_for_source(
        session,
        source_table=KNOCKOFF_SOURCE_TABLE,
        source_id=payment_id,
        party_id=party_id,
        txn_date=payment_date,
        txn_type=LedgerTxnType.settlement_discount,
        doc_no=voucher_no,
        debit=debit,
        credit=credit,
        narration=reason or "Settlement discount",
    )


async def _post_bank_leg(
    session: AsyncSession,
    *,
    payment_id: int,
    bank_id: int,
    payment_date: date,
    direction: PaymentDirection,
    amount: Decimal,
    voucher_no: str,
    narration: str | None,
) -> None:
    """Post (or replace) the bank ledger leg. Computes its own debit/credit
    via _bank_txn_type_and_sign rather than accepting the party leg's
    values — see that function for why they're not the same pair.
    """
    txn_type, debit, credit = _bank_txn_type_and_sign(direction, amount)
    await bank_ledger.repost_for_source(
        session,
        source_table="payments",
        source_id=payment_id,
        bank_id=bank_id,
        txn_date=payment_date,
        txn_type=txn_type,
        doc_no=voucher_no,
        debit=debit,
        credit=credit,
        narration=narration,
    )


async def _post_cash_leg(
    session: AsyncSession,
    *,
    payment_id: int,
    payment_date: date,
    direction: PaymentDirection,
    amount: Decimal,
    voucher_no: str,
    narration: str | None,
) -> None:
    """Post (or replace) the cash ledger leg. Same sign as the bank leg
    (receipt = cash in = debit), so it deliberately reuses
    _bank_txn_type_and_sign rather than the party leg's pair. Only the
    real amount received/paid goes here — never the knockoff.
    """
    txn_type, debit, credit = _bank_txn_type_and_sign(direction, amount)
    await cash_ledger.repost_for_source(
        session,
        source_table="payments",
        source_id=payment_id,
        txn_date=payment_date,
        txn_type=txn_type,
        doc_no=voucher_no,
        debit=debit,
        credit=credit,
        narration=narration,
    )


async def _post_transfer_leg(
    session: AsyncSession,
    *,
    payment_id: int,
    vendor: Party,
    transfer_amount: Decimal,
    payment_date: date,
    voucher_no: str,
    from_party_name: str,
) -> None:
    """Post (or replace) the payment_transfer ledger leg. `vendor` must
    already be validated — this does no lookups of its own, on purpose:
    see the "validate before writing" note on both callers below.
    """
    await ledger.repost_for_source(
        session,
        source_table=TRANSFER_SOURCE_TABLE,
        source_id=payment_id,
        party_id=vendor.id,
        txn_date=payment_date,
        txn_type=LedgerTxnType.payment,
        doc_no=voucher_no,
        debit=transfer_amount,
        credit=Decimal("0"),
        narration=f"Transfer from {from_party_name}'s payment {voucher_no}",
    )


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentWrite,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Payment:
    party = await session.get(Party, body.party_id)
    if party is None or not party.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Party not found or inactive")

    # Validated before anything is written: a payment row with a
    # transfer_to_party_id or bank_id pointing nowhere would fail as a raw
    # foreign-key violation at flush time, not this clean 400.
    vendor: Party | None = None
    if body.transfer_to_party_id is not None:
        vendor = await _load_transfer_target(session, body.transfer_to_party_id)
    bank: Bank | None = None
    if body.bank_id is not None:
        bank = await _load_bank(session, body.bank_id)

    if body.knockoff_amount is not None:
        await _check_knockoff(
            session,
            party_id=body.party_id,
            direction=body.direction,
            knockoff=body.knockoff_amount,
            exclude_payment_id=None,
        )

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
        transfer_to_party_id=body.transfer_to_party_id,
        transfer_amount=body.transfer_amount,
        bank_id=body.bank_id,
        knockoff_amount=body.knockoff_amount,
        knockoff_reason=body.knockoff_reason,
        created_by=current_user.id,
    )
    session.add(payment)
    await session.flush()

    # Leg 1: the customer is credited for the FULL amount received,
    # regardless of whether any of it gets transferred on — unchanged
    # from a plain payment.
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

    # Leg 2, only if a transfer was requested: the vendor is debited for
    # the transfer amount only. The untransferred remainder needs no
    # entry of its own — it's cash retained, already reflected in leg 1.
    if vendor is not None:
        assert body.transfer_amount is not None  # PaymentWrite guarantees the pair
        await _post_transfer_leg(
            session,
            payment_id=payment.id,
            vendor=vendor,
            transfer_amount=body.transfer_amount,
            payment_date=body.payment_date,
            voucher_no=voucher_no,
            from_party_name=party.name,
        )

    # Settlement-discount line: same party, same side as leg 1.
    if body.knockoff_amount is not None:
        await _post_knockoff_leg(
            session,
            payment_id=payment.id,
            party_id=body.party_id,
            direction=body.direction,
            knockoff=body.knockoff_amount,
            payment_date=body.payment_date,
            voucher_no=voucher_no,
            reason=body.knockoff_reason,
        )

    # Cash leg: cash mode with no vendor transfer (a transfer is a hand-off,
    # never a cash-book entry — same rule as the bank leg).
    if body.is_cash and vendor is None:
        await _post_cash_leg(
            session,
            payment_id=payment.id,
            payment_date=body.payment_date,
            direction=body.direction,
            amount=body.amount,
            voucher_no=voucher_no,
            narration=body.narration,
        )

    # Bank leg, only if a bank was selected (mutually exclusive with the
    # transfer above — PaymentWrite guarantees exactly one applies).
    if bank is not None:
        await _post_bank_leg(
            session,
            payment_id=payment.id,
            bank_id=bank.id,
            payment_date=body.payment_date,
            direction=body.direction,
            amount=body.amount,
            voucher_no=voucher_no,
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

    # Same ordering as create_payment: validate before this ORM object is
    # touched, so a bad vendor/bank id 400s cleanly instead of surfacing as
    # a foreign-key violation when the UPDATE is flushed.
    vendor: Party | None = None
    if body.transfer_to_party_id is not None:
        vendor = await _load_transfer_target(session, body.transfer_to_party_id)
    bank: Bank | None = None
    if body.bank_id is not None:
        bank = await _load_bank(session, body.bank_id)

    if body.knockoff_amount is not None:
        await _check_knockoff(
            session,
            party_id=body.party_id,
            direction=body.direction,
            knockoff=body.knockoff_amount,
            exclude_payment_id=payment.id,
        )

    payment.party_id = body.party_id
    payment.payment_date = body.payment_date
    payment.amount = body.amount
    payment.mode = body.mode
    payment.reference_no = body.reference_no
    payment.narration = body.narration
    payment.transfer_to_party_id = body.transfer_to_party_id
    payment.transfer_amount = body.transfer_amount
    payment.bank_id = body.bank_id
    payment.knockoff_amount = body.knockoff_amount
    payment.knockoff_reason = body.knockoff_reason

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

    # Keeps the second leg in step with the edit: reposted if a transfer
    # is (still, or newly) present, removed if it was dropped. Without
    # this an edit that changes or clears the transfer would leave the
    # vendor's ledger wrong while the payment record itself looked fine.
    if vendor is not None:
        assert body.transfer_amount is not None  # PaymentWrite guarantees the pair
        await _post_transfer_leg(
            session,
            payment_id=payment.id,
            vendor=vendor,
            transfer_amount=body.transfer_amount,
            payment_date=body.payment_date,
            voucher_no=payment.voucher_no,
            from_party_name=party.name,
        )
    else:
        await ledger.remove_for_source(session, source_table=TRANSFER_SOURCE_TABLE, source_id=payment.id)

    if body.knockoff_amount is not None:
        await _post_knockoff_leg(
            session,
            payment_id=payment.id,
            party_id=body.party_id,
            direction=body.direction,
            knockoff=body.knockoff_amount,
            payment_date=body.payment_date,
            voucher_no=payment.voucher_no,
            reason=body.knockoff_reason,
        )
    else:
        await ledger.remove_for_source(session, source_table=KNOCKOFF_SOURCE_TABLE, source_id=payment.id)

    if body.is_cash and vendor is None:
        await _post_cash_leg(
            session,
            payment_id=payment.id,
            payment_date=body.payment_date,
            direction=body.direction,
            amount=body.amount,
            voucher_no=payment.voucher_no,
            narration=body.narration,
        )
    else:
        await cash_ledger.remove_for_source(session, source_table="payments", source_id=payment.id)

    # Same idea for the bank leg — reposted if a bank is (still, or newly)
    # selected, removed if it was cleared.
    if bank is not None:
        await _post_bank_leg(
            session,
            payment_id=payment.id,
            bank_id=bank.id,
            payment_date=body.payment_date,
            direction=body.direction,
            amount=body.amount,
            voucher_no=payment.voucher_no,
            narration=body.narration,
        )
    else:
        await bank_ledger.remove_for_source(session, source_table="payments", source_id=payment.id)

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
    # Unconditional and idempotent — a no-op for legs that were never
    # posted (a payment has at most one of transfer/bank), and removes
    # whichever one was. Either way every leg of this payment is gone.
    await ledger.remove_for_source(session, source_table=TRANSFER_SOURCE_TABLE, source_id=payment.id)
    await ledger.remove_for_source(session, source_table=KNOCKOFF_SOURCE_TABLE, source_id=payment.id)
    await bank_ledger.remove_for_source(session, source_table="payments", source_id=payment.id)
    await cash_ledger.remove_for_source(session, source_table="payments", source_id=payment.id)

    await session.commit()
    await session.refresh(payment)
    return payment
