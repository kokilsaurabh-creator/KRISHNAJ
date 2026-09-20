"""The cash ledger service — the only code allowed to write to
cash_ledger_entries. Mirrors bank_ledger.py for the one, single cash
account: no function here commits, the caller's transaction is the unit
of work, and the balance is SUM(debit) - SUM(credit), computed on every
read and never stored.

Sign convention, same as the bank ledger: cash in -> debit, cash out ->
credit; positive balance = cash in hand. So a receipt is a DEBIT here
(and a credit on the party ledger) — opposite sides, same payment. See
routers/payments.py's _bank_txn_type_and_sign, which the cash leg reuses
for exactly that reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CashAccount, CashLedgerEntry, LedgerTxnType, Party, Payment
from app.services.bank_ledger import _money
from app.services.ledger import DuplicatePostingError, InvalidDateRangeError, InvalidLedgerAmountError

CASH_ACCOUNT_ID = 1


@dataclass(frozen=True)
class CashLedgerRow:
    id: int
    txn_date: date
    txn_type: LedgerTxnType
    doc_no: str | None
    narration: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal
    party_name: str | None


@dataclass(frozen=True)
class CashLedgerReport:
    from_date: date
    to_date: date
    opening: Decimal
    rows: list[CashLedgerRow]
    total_debit: Decimal
    total_credit: Decimal
    closing: Decimal


async def post_to_cash_ledger(
    session: AsyncSession,
    *,
    txn_date: date,
    txn_type: LedgerTxnType,
    source_table: str | None,
    source_id: int | None,
    doc_no: str | None,
    debit: Decimal,
    credit: Decimal,
    narration: str | None = None,
) -> CashLedgerEntry:
    """Insert one cash ledger row. Does not commit; flushes only."""
    debit = _money(debit, field_name="debit")
    credit = _money(credit, field_name="credit")

    if debit < 0 or credit < 0:
        raise InvalidLedgerAmountError("debit and credit must both be >= 0")
    if debit > 0 and credit > 0:
        raise InvalidLedgerAmountError("a cash ledger row cannot have both debit and credit set")
    if debit == 0 and credit == 0:
        raise InvalidLedgerAmountError("a cash ledger row must have a nonzero debit or credit")

    if (source_table is None) != (source_id is None):
        raise ValueError("source_table and source_id must be both set or both None")

    if source_table is not None:
        existing = await session.execute(
            select(CashLedgerEntry.id).where(
                CashLedgerEntry.source_table == source_table,
                CashLedgerEntry.source_id == source_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DuplicatePostingError(
                f"cash_ledger_entries already has a row for {source_table}:{source_id} — "
                "use repost_for_source to replace it"
            )

    entry = CashLedgerEntry(
        txn_date=txn_date,
        txn_type=txn_type,
        source_table=source_table,
        source_id=source_id,
        doc_no=doc_no,
        debit=debit,
        credit=credit,
        narration=narration,
    )
    session.add(entry)
    await session.flush()
    return entry


async def remove_for_source(session: AsyncSession, *, source_table: str, source_id: int) -> int:
    """Delete the cash ledger row for (source_table, source_id), if any.
    Idempotent. Does not commit."""
    result = await session.execute(
        delete(CashLedgerEntry).where(
            CashLedgerEntry.source_table == source_table,
            CashLedgerEntry.source_id == source_id,
        )
    )
    await session.flush()
    return result.rowcount or 0


async def repost_for_source(
    session: AsyncSession,
    *,
    source_table: str,
    source_id: int,
    txn_date: date,
    txn_type: LedgerTxnType,
    doc_no: str | None,
    debit: Decimal,
    credit: Decimal,
    narration: str | None = None,
) -> CashLedgerEntry:
    """Replace the cash ledger row for (source_table, source_id). Does not commit."""
    await remove_for_source(session, source_table=source_table, source_id=source_id)
    return await post_to_cash_ledger(
        session,
        txn_date=txn_date,
        txn_type=txn_type,
        source_table=source_table,
        source_id=source_id,
        doc_no=doc_no,
        debit=debit,
        credit=credit,
        narration=narration,
    )


async def get_cash_account(session: AsyncSession) -> CashAccount | None:
    return await session.get(CashAccount, CASH_ACCOUNT_ID)


async def set_opening_balance(
    session: AsyncSession,
    *,
    as_of_date: date,
    amount: Decimal,
    user_id: int,
    narration: str | None = "Opening balance",
) -> CashAccount:
    """Set (or replace) the cash opening balance. Idempotent: the single
    cash_account row is upserted and the one opening ledger row replaced,
    so re-saving never adds a second. The ledger row is what the balance
    is computed from; cash_account keeps the entered value for display.
    amount=0 clears the ledger row. Does not commit.
    """
    amount = _money(amount, field_name="amount")

    account = await get_cash_account(session)
    if account is None:
        account = CashAccount(
            id=CASH_ACCOUNT_ID, opening_balance=amount, opening_balance_date=as_of_date, created_by=user_id
        )
        session.add(account)
    else:
        account.opening_balance = amount
        account.opening_balance_date = as_of_date

    await session.execute(
        delete(CashLedgerEntry).where(
            CashLedgerEntry.txn_type == LedgerTxnType.opening,
            CashLedgerEntry.source_table.is_(None),
        )
    )
    await session.flush()

    if amount != 0:
        await post_to_cash_ledger(
            session,
            txn_date=as_of_date,
            txn_type=LedgerTxnType.opening,
            source_table=None,
            source_id=None,
            doc_no=None,
            debit=amount if amount > 0 else Decimal("0"),
            credit=-amount if amount < 0 else Decimal("0"),
            narration=narration,
        )
    return account


async def get_cash_ledger(session: AsyncSession, from_date: date, to_date: date) -> CashLedgerReport:
    """Opening balance, dated rows with a running balance, totals and
    closing over [from_date, to_date] inclusive. Computed on every call."""
    if from_date > to_date:
        raise InvalidDateRangeError("from_date must be on or before to_date")

    opening_result = await session.execute(
        select(func.coalesce(func.sum(CashLedgerEntry.debit - CashLedgerEntry.credit), 0)).where(
            CashLedgerEntry.txn_date < from_date
        )
    )
    opening = _money(opening_result.scalar_one(), field_name="opening")

    rows_result = await session.execute(
        select(CashLedgerEntry)
        .where(CashLedgerEntry.txn_date >= from_date, CashLedgerEntry.txn_date <= to_date)
        .order_by(CashLedgerEntry.txn_date, CashLedgerEntry.id)
    )
    entries = rows_result.scalars().all()

    payment_ids = {e.source_id for e in entries if e.source_table == "payments" and e.source_id is not None}
    party_name_by_payment_id: dict[int, str] = {}
    if payment_ids:
        party_rows = await session.execute(
            select(Payment.id, Party.name).join(Party, Party.id == Payment.party_id).where(Payment.id.in_(payment_ids))
        )
        party_name_by_payment_id = dict(party_rows.all())

    rows: list[CashLedgerRow] = []
    running = opening
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for entry in entries:
        running = running + entry.debit - entry.credit
        total_debit += entry.debit
        total_credit += entry.credit
        rows.append(
            CashLedgerRow(
                id=entry.id,
                txn_date=entry.txn_date,
                txn_type=entry.txn_type,
                doc_no=entry.doc_no,
                narration=entry.narration,
                debit=entry.debit,
                credit=entry.credit,
                balance=running,
                party_name=party_name_by_payment_id.get(entry.source_id) if entry.source_table == "payments" else None,
            )
        )

    return CashLedgerReport(
        from_date=from_date,
        to_date=to_date,
        opening=opening,
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        closing=opening + total_debit - total_credit,
    )
