"""The bank ledger service — the only code in this project allowed to
write to bank_ledger_entries. Same discipline as ledger.py, one table
over: no function here commits, the caller's transaction is the unit of
work, and a bank's balance is SUM(debit) - SUM(credit), computed on every
read rather than stored anywhere.

Sign convention (per the bank-tracking design):
    deposit (money in)     -> debit
    withdrawal (money out) -> credit
    balance = SUM(debit) - SUM(credit); positive = money in the bank.

Both ledgers use "debit increases the balance," but that does NOT mean a
given payment posts the same side on both. A receipt is a CREDIT on the
party ledger (it reduces what they owe) and a DEBIT here (money just
landed in the bank) — opposite sides, same payment. See
routers/payments.py's _bank_txn_type_and_sign for where that gets
computed; do not assume the party leg's debit/credit can be reused
as-is for a bank leg.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BankLedgerEntry, LedgerTxnType, Party, Payment
from app.services.ledger import DuplicatePostingError, InvalidDateRangeError, InvalidLedgerAmountError

TWO_PLACES = Decimal("0.01")


def _money(value: Decimal | int | str, *, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(
            f"{field_name} must be a Decimal (or int/str), not float — this ledger never uses floats for money."
        )
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class BankLedgerRow:
    id: int
    txn_date: date
    txn_type: LedgerTxnType
    doc_no: str | None
    narration: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal
    # Resolved from the payment this row came from — bank_ledger_entries
    # has no party_id of its own, only source_table/source_id. None for
    # the opening-balance row (source_table is None there) or if the
    # payment or its party has since been deleted, neither of which this
    # app actually does.
    party_name: str | None


@dataclass(frozen=True)
class BankLedgerReport:
    bank_id: int
    from_date: date
    to_date: date
    opening: Decimal
    rows: list[BankLedgerRow]
    total_debit: Decimal
    total_credit: Decimal
    closing: Decimal


async def post_to_bank_ledger(
    session: AsyncSession,
    *,
    bank_id: int,
    txn_date: date,
    txn_type: LedgerTxnType,
    source_table: str | None,
    source_id: int | None,
    doc_no: str | None,
    debit: Decimal,
    credit: Decimal,
    narration: str | None = None,
) -> BankLedgerEntry:
    """Insert one bank ledger row. Does not commit; flushes only, so the
    duplicate check below sees prior writes made earlier in the same
    transaction."""
    debit = _money(debit, field_name="debit")
    credit = _money(credit, field_name="credit")

    if debit < 0 or credit < 0:
        raise InvalidLedgerAmountError("debit and credit must both be >= 0")
    if debit > 0 and credit > 0:
        raise InvalidLedgerAmountError("a bank ledger row cannot have both debit and credit set")
    if debit == 0 and credit == 0:
        raise InvalidLedgerAmountError("a bank ledger row must have a nonzero debit or credit")

    if (source_table is None) != (source_id is None):
        raise ValueError("source_table and source_id must be both set or both None")

    if source_table is not None:
        existing = await session.execute(
            select(BankLedgerEntry.id).where(
                BankLedgerEntry.source_table == source_table,
                BankLedgerEntry.source_id == source_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DuplicatePostingError(
                f"bank_ledger_entries already has a row for {source_table}:{source_id} — "
                "use repost_for_source to replace it"
            )

    entry = BankLedgerEntry(
        bank_id=bank_id,
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


async def repost_for_source(
    session: AsyncSession,
    *,
    source_table: str,
    source_id: int,
    bank_id: int,
    txn_date: date,
    txn_type: LedgerTxnType,
    doc_no: str | None,
    debit: Decimal,
    credit: Decimal,
    narration: str | None = None,
) -> BankLedgerEntry:
    """Replace the bank ledger row for (source_table, source_id): delete,
    then re-insert with the new values. Does not commit."""
    await remove_for_source(session, source_table=source_table, source_id=source_id)
    return await post_to_bank_ledger(
        session,
        bank_id=bank_id,
        txn_date=txn_date,
        txn_type=txn_type,
        source_table=source_table,
        source_id=source_id,
        doc_no=doc_no,
        debit=debit,
        credit=credit,
        narration=narration,
    )


async def remove_for_source(session: AsyncSession, *, source_table: str, source_id: int) -> int:
    """Delete the bank ledger row for (source_table, source_id), if any.
    Idempotent: removing an already-absent row just returns 0. Does not
    commit."""
    result = await session.execute(
        delete(BankLedgerEntry).where(
            BankLedgerEntry.source_table == source_table,
            BankLedgerEntry.source_id == source_id,
        )
    )
    await session.flush()
    return result.rowcount or 0


async def set_opening_balance(
    session: AsyncSession,
    *,
    bank_id: int,
    as_of_date: date,
    amount: Decimal,
    narration: str | None = None,
) -> BankLedgerEntry | None:
    """Set (or replace) a bank's opening balance. Idempotent: re-posting
    replaces the existing opening row for this bank rather than adding a
    second one — same rule as the party ledger's opening balance, keyed
    on (bank_id, txn_type='opening') since opening rows have no
    source_table/source_id.

    amount=0 clears the opening balance (deletes the row, returns None)
    rather than posting a meaningless zero row.
    """
    amount = _money(amount, field_name="amount")

    existing = await session.execute(
        select(BankLedgerEntry.id).where(
            BankLedgerEntry.bank_id == bank_id,
            BankLedgerEntry.txn_type == LedgerTxnType.opening,
            BankLedgerEntry.source_table.is_(None),
        )
    )
    existing_id = existing.scalar_one_or_none()
    if existing_id is not None:
        await session.execute(delete(BankLedgerEntry).where(BankLedgerEntry.id == existing_id))
        await session.flush()

    if amount == 0:
        return None

    return await post_to_bank_ledger(
        session,
        bank_id=bank_id,
        txn_date=as_of_date,
        txn_type=LedgerTxnType.opening,
        source_table=None,
        source_id=None,
        doc_no=None,
        debit=amount if amount > 0 else Decimal("0"),
        credit=-amount if amount < 0 else Decimal("0"),
        narration=narration,
    )


async def get_bank_ledger(
    session: AsyncSession,
    bank_id: int,
    from_date: date,
    to_date: date,
) -> BankLedgerReport:
    """Opening balance, dated rows with a running balance, totals, and
    closing for one bank over [from_date, to_date] inclusive. The running
    balance is computed here on every call — it is never stored."""
    if from_date > to_date:
        raise InvalidDateRangeError("from_date must be on or before to_date")

    opening_result = await session.execute(
        select(func.coalesce(func.sum(BankLedgerEntry.debit - BankLedgerEntry.credit), 0)).where(
            BankLedgerEntry.bank_id == bank_id,
            BankLedgerEntry.txn_date < from_date,
        )
    )
    opening = _money(opening_result.scalar_one(), field_name="opening")

    rows_result = await session.execute(
        select(BankLedgerEntry)
        .where(
            BankLedgerEntry.bank_id == bank_id,
            BankLedgerEntry.txn_date >= from_date,
            BankLedgerEntry.txn_date <= to_date,
        )
        .order_by(BankLedgerEntry.txn_date, BankLedgerEntry.id)
    )
    entries = rows_result.scalars().all()

    # Every non-opening row's source_table is 'payments' (see
    # routers/payments.py) — one batched join instead of a lookup per
    # row, since a bank's statement can run to hundreds of entries.
    payment_ids = {e.source_id for e in entries if e.source_table == "payments" and e.source_id is not None}
    party_name_by_payment_id: dict[int, str] = {}
    if payment_ids:
        party_rows = await session.execute(
            select(Payment.id, Party.name).join(Party, Party.id == Payment.party_id).where(Payment.id.in_(payment_ids))
        )
        party_name_by_payment_id = dict(party_rows.all())

    rows: list[BankLedgerRow] = []
    running = opening
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for entry in entries:
        running = running + entry.debit - entry.credit
        total_debit += entry.debit
        total_credit += entry.credit
        rows.append(
            BankLedgerRow(
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

    closing = opening + total_debit - total_credit

    return BankLedgerReport(
        bank_id=bank_id,
        from_date=from_date,
        to_date=to_date,
        opening=opening,
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        closing=closing,
    )
