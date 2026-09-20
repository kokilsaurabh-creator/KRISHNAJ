"""The ledger service — the only code in this project allowed to write to
ledger_entries.

Sign convention (spec section 2, "Sign convention"):
    sale            -> debit  = net_amount
    receipt (in)    -> credit = amount
    purchase        -> credit = net_amount
    payment (out)   -> debit  = amount
    balance = SUM(debit) - SUM(credit); positive = receivable.

None of these functions call session.commit(). The document write (sale /
purchase / payment) and its ledger post must share one caller-managed
transaction, per the spec's non-negotiable write rule: if the ledger post
fails, the document must not exist either.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LedgerEntry, LedgerTxnType, Party, PartyType

TWO_PLACES = Decimal("0.01")


class LedgerError(Exception):
    """Base class for ledger service errors."""


class DuplicatePostingError(LedgerError):
    """Raised when (source_table, source_id) already has a ledger row.

    Backed by the unique partial index idx_ledger_source, but checked with
    a plain SELECT first so a duplicate post fails cleanly instead of
    aborting the caller's transaction with a raw IntegrityError. The index
    remains the authoritative guard against a race between the check and
    the insert; see the README note on this in the review write-up.
    """


class InvalidLedgerAmountError(LedgerError):
    """Raised when a debit/credit pair is not a valid single-sided posting."""


class InvalidDateRangeError(LedgerError):
    """Raised when from_date is after to_date."""


def _money(value: Decimal | int | str, *, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(
            f"{field_name} must be a Decimal (or int/str), not float — "
            "this ledger never uses floats for money."
        )
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LedgerRow:
    id: int
    txn_date: date
    txn_type: LedgerTxnType
    doc_no: str | None
    narration: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal


@dataclass(frozen=True)
class LedgerReport:
    party_id: int
    from_date: date
    to_date: date
    opening: Decimal
    rows: list[LedgerRow]
    total_debit: Decimal
    total_credit: Decimal
    closing: Decimal


@dataclass(frozen=True)
class OutstandingRow:
    party_id: int
    party_name: str
    party_type: PartyType
    balance: Decimal


@dataclass(frozen=True)
class OutstandingReport:
    party_type: PartyType | None
    as_on_date: date
    rows: list[OutstandingRow]
    receivable_total: Decimal
    payable_total: Decimal


async def post_to_ledger(
    session: AsyncSession,
    *,
    party_id: int,
    txn_date: date,
    txn_type: LedgerTxnType,
    source_table: str | None,
    source_id: int | None,
    doc_no: str | None,
    debit: Decimal,
    credit: Decimal,
    narration: str | None = None,
) -> LedgerEntry:
    """Insert one ledger row.

    Route handlers must call this (or repost_for_source) rather than
    constructing a LedgerEntry themselves — that's what "no ledger writes
    outside ledger.py" means in practice.

    Does not commit; flushes only, so the duplicate check below sees any
    prior writes made earlier in the same transaction.
    """
    debit = _money(debit, field_name="debit")
    credit = _money(credit, field_name="credit")

    if debit < 0 or credit < 0:
        raise InvalidLedgerAmountError("debit and credit must both be >= 0")
    if debit > 0 and credit > 0:
        raise InvalidLedgerAmountError("a ledger row cannot have both debit and credit set")
    if debit == 0 and credit == 0:
        raise InvalidLedgerAmountError("a ledger row must have a nonzero debit or credit")

    if (source_table is None) != (source_id is None):
        raise ValueError("source_table and source_id must be both set or both None")

    if source_table is not None:
        existing = await session.execute(
            select(LedgerEntry.id).where(
                LedgerEntry.source_table == source_table,
                LedgerEntry.source_id == source_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DuplicatePostingError(
                f"ledger_entries already has a row for {source_table}:{source_id} — "
                "use repost_for_source to replace it"
            )

    entry = LedgerEntry(
        party_id=party_id,
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
    party_id: int,
    txn_date: date,
    txn_type: LedgerTxnType,
    doc_no: str | None,
    debit: Decimal,
    credit: Decimal,
    narration: str | None = None,
) -> LedgerEntry:
    """Replace the ledger row for (source_table, source_id): delete, then
    re-insert with the new values. Used when a sale/purchase/payment is
    edited. Does not commit.
    """
    await remove_for_source(session, source_table=source_table, source_id=source_id)
    return await post_to_ledger(
        session,
        party_id=party_id,
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
    """Delete the ledger row for (source_table, source_id), if any.

    Used on cancel. Idempotent: removing an already-absent row is not an
    error, it just returns 0. Does not commit.
    """
    result = await session.execute(
        delete(LedgerEntry).where(
            LedgerEntry.source_table == source_table,
            LedgerEntry.source_id == source_id,
        )
    )
    await session.flush()
    return result.rowcount or 0


async def set_opening_balance(
    session: AsyncSession,
    *,
    party_id: int,
    as_of_date: date,
    amount: Decimal,
    narration: str | None = None,
) -> LedgerEntry | None:
    """Set (or replace) a party's opening balance.

    Idempotent, per the spec: re-posting replaces the existing opening row
    for this party rather than adding a second one. Opening rows have no
    source_table/source_id (that's what makes them 'opening' rather than
    document-backed), so they aren't covered by the idempotency guarantee the
    partial unique index gives every other txn_type — this function is
    where that same guarantee gets enforced for opening balances specifically,
    keyed on (party_id, txn_type='opening') instead.

    amount follows the same sign convention as everywhere else: positive =
    they owe us (debit), negative = we owe them (credit). amount=0 clears
    the opening balance (deletes the row, returns None) rather than posting
    a meaningless zero row.
    """
    amount = _money(amount, field_name="amount")

    existing = await session.execute(
        select(LedgerEntry.id).where(
            LedgerEntry.party_id == party_id,
            LedgerEntry.txn_type == LedgerTxnType.opening,
            LedgerEntry.source_table.is_(None),
        )
    )
    existing_id = existing.scalar_one_or_none()
    if existing_id is not None:
        await session.execute(delete(LedgerEntry).where(LedgerEntry.id == existing_id))
        await session.flush()

    if amount == 0:
        return None

    return await post_to_ledger(
        session,
        party_id=party_id,
        txn_date=as_of_date,
        txn_type=LedgerTxnType.opening,
        source_table=None,
        source_id=None,
        doc_no=None,
        debit=amount if amount > 0 else Decimal("0"),
        credit=-amount if amount < 0 else Decimal("0"),
        narration=narration,
    )


async def get_ledger(
    session: AsyncSession,
    party_id: int,
    from_date: date,
    to_date: date,
) -> LedgerReport:
    """Opening balance, dated rows with a running balance, totals, and
    closing for one party over [from_date, to_date] inclusive. The running
    balance is computed here on every call — it is never stored.
    """
    if from_date > to_date:
        raise InvalidDateRangeError("from_date must be on or before to_date")

    opening_result = await session.execute(
        select(func.coalesce(func.sum(LedgerEntry.debit - LedgerEntry.credit), 0)).where(
            LedgerEntry.party_id == party_id,
            LedgerEntry.txn_date < from_date,
        )
    )
    opening = _money(opening_result.scalar_one(), field_name="opening")

    rows_result = await session.execute(
        select(LedgerEntry)
        .where(
            LedgerEntry.party_id == party_id,
            LedgerEntry.txn_date >= from_date,
            LedgerEntry.txn_date <= to_date,
        )
        .order_by(LedgerEntry.txn_date, LedgerEntry.id)
    )
    entries = rows_result.scalars().all()

    rows: list[LedgerRow] = []
    running = opening
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for entry in entries:
        running = running + entry.debit - entry.credit
        total_debit += entry.debit
        total_credit += entry.credit
        rows.append(
            LedgerRow(
                id=entry.id,
                txn_date=entry.txn_date,
                txn_type=entry.txn_type,
                doc_no=entry.doc_no,
                narration=entry.narration,
                debit=entry.debit,
                credit=entry.credit,
                balance=running,
            )
        )

    closing = opening + total_debit - total_credit

    return LedgerReport(
        party_id=party_id,
        from_date=from_date,
        to_date=to_date,
        opening=opening,
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        closing=closing,
    )


async def get_party_balance(
    session: AsyncSession,
    party_id: int,
    *,
    exclude_payment_id: int | None = None,
) -> Decimal:
    """SUM(debit) - SUM(credit) over the party's whole ledger (positive =
    they owe us). exclude_payment_id leaves out that payment's own legs so
    an edit can be validated against the balance as it stood before it.
    """
    stmt = select(func.coalesce(func.sum(LedgerEntry.debit - LedgerEntry.credit), 0)).where(
        LedgerEntry.party_id == party_id
    )
    if exclude_payment_id is not None:
        stmt = stmt.where(
            or_(
                LedgerEntry.source_table.is_(None),
                LedgerEntry.source_table.not_in(["payments", "payment_knockoff"]),
                LedgerEntry.source_id != exclude_payment_id,
            )
        )
    result = await session.execute(stmt)
    return _money(result.scalar_one(), field_name="balance")


async def get_outstanding(
    session: AsyncSession,
    party_type: PartyType | None,
    as_on_date: date,
) -> OutstandingReport:
    """Closing balance for every active party as on a date, most useful for
    the /reports/outstanding screen (and, later, /dashboard/summary — this
    is the same computation, just call it with party_type=None).

    Row inclusion vs. header totals are deliberately different rules:

    - Rows: party_type='customer' or 'supplier' also includes parties typed
      'both', since a 'both' party can carry a balance on either side and
      should be visible on both reports regardless of which way it
      currently leans.
    - Totals: receivable_total sums only the positive-balance rows;
      payable_total sums only the negative-balance rows (as a positive
      amount). A row whose balance sign is the "wrong" way for the report
      it's on (e.g. a customer who's in credit) still appears in `rows` —
      the frontend labels that one "Advance" — but contributes zero to
      either total, so the header figures stay meaningful summaries rather
      than being dragged around by exceptions.
    """
    balance_expr = func.coalesce(func.sum(LedgerEntry.debit - LedgerEntry.credit), 0).label("balance")

    stmt = (
        select(Party.id, Party.name, Party.party_type, balance_expr)
        .outerjoin(
            LedgerEntry,
            (LedgerEntry.party_id == Party.id) & (LedgerEntry.txn_date <= as_on_date),
        )
        .where(Party.is_active.is_(True))
        .group_by(Party.id, Party.name, Party.party_type)
        .order_by(Party.name)
    )

    if party_type is not None:
        if party_type == PartyType.both:
            stmt = stmt.where(Party.party_type == PartyType.both)
        else:
            stmt = stmt.where(Party.party_type.in_([party_type, PartyType.both]))

    result = await session.execute(stmt)

    rows = [
        OutstandingRow(
            party_id=row.id,
            party_name=row.name,
            party_type=row.party_type,
            balance=_money(row.balance, field_name="balance"),
        )
        for row in result.all()
    ]

    receivable_total = sum((r.balance for r in rows if r.balance > 0), Decimal("0.00"))
    payable_total = sum((-r.balance for r in rows if r.balance < 0), Decimal("0.00"))

    return OutstandingReport(
        party_type=party_type,
        as_on_date=as_on_date,
        rows=rows,
        receivable_total=receivable_total,
        payable_total=payable_total,
    )
