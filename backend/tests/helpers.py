"""Tiny stand-ins for the sales/purchases/payments route handlers that don't
exist yet. Each one does exactly what a real route will do: write the
document row and post to the ledger in the same transaction, then commit.
Used so ledger.py can be exercised against realistic data without any
routes or auth in place.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LedgerTxnType, Party, Payment, PaymentDirection, Purchase, Sale, User
from app.services import ledger


async def create_sale(
    session: AsyncSession,
    *,
    party: Party,
    user: User,
    invoice_no: str,
    amount: Decimal,
    txn_date: date,
    narration: str | None = None,
) -> Sale:
    sale = Sale(
        invoice_no=invoice_no,
        invoice_date=txn_date,
        party_id=party.id,
        gross_amount=amount,
        discount=Decimal("0"),
        net_amount=amount,
        narration=narration,
        created_by=user.id,
    )
    session.add(sale)
    await session.flush()
    await ledger.post_to_ledger(
        session,
        party_id=party.id,
        txn_date=txn_date,
        txn_type=LedgerTxnType.sale,
        source_table="sales",
        source_id=sale.id,
        doc_no=invoice_no,
        debit=amount,
        credit=Decimal("0"),
        narration=narration,
    )
    await session.commit()
    await session.refresh(sale)
    return sale


async def create_purchase(
    session: AsyncSession,
    *,
    party: Party,
    user: User,
    bill_no: str,
    amount: Decimal,
    txn_date: date,
    narration: str | None = None,
) -> Purchase:
    purchase = Purchase(
        bill_no=bill_no,
        bill_date=txn_date,
        party_id=party.id,
        gross_amount=amount,
        discount=Decimal("0"),
        net_amount=amount,
        narration=narration,
        created_by=user.id,
    )
    session.add(purchase)
    await session.flush()
    await ledger.post_to_ledger(
        session,
        party_id=party.id,
        txn_date=txn_date,
        txn_type=LedgerTxnType.purchase,
        source_table="purchases",
        source_id=purchase.id,
        doc_no=bill_no,
        debit=Decimal("0"),
        credit=amount,
        narration=narration,
    )
    await session.commit()
    await session.refresh(purchase)
    return purchase


async def create_payment(
    session: AsyncSession,
    *,
    party: Party,
    user: User,
    voucher_no: str,
    amount: Decimal,
    direction: PaymentDirection,
    txn_date: date,
    mode: str = "Cash",
    narration: str | None = None,
) -> Payment:
    payment = Payment(
        voucher_no=voucher_no,
        payment_date=txn_date,
        party_id=party.id,
        direction=direction,
        amount=amount,
        mode=mode,
        narration=narration,
        created_by=user.id,
    )
    session.add(payment)
    await session.flush()

    txn_type = LedgerTxnType.receipt if direction == PaymentDirection.IN else LedgerTxnType.payment
    debit = amount if direction == PaymentDirection.OUT else Decimal("0")
    credit = amount if direction == PaymentDirection.IN else Decimal("0")

    await ledger.post_to_ledger(
        session,
        party_id=party.id,
        txn_date=txn_date,
        txn_type=txn_type,
        source_table="payments",
        source_id=payment.id,
        doc_no=voucher_no,
        debit=debit,
        credit=credit,
        narration=narration,
    )
    await session.commit()
    await session.refresh(payment)
    return payment
