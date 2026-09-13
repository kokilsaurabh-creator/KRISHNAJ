"""Sequential document numbering (invoice numbers, voucher numbers).

Concurrency is the whole point of this module: two requests hitting Save at
the same moment (double-tap over a slow connection, two staff on different
terminals) must never get the same number. `allocate_doc_number` takes a
row lock on the relevant doc_sequences row with SELECT ... FOR UPDATE, so
the second caller blocks at the database level until the first one's
transaction commits or rolls back — there is no read-then-write gap for a
race to land in.

Must be called inside the same transaction as the document insert it's
numbering, same as ledger.py — if the caller rolls back, the number
allocation rolls back with it and the number is free again.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocSequence

_FY_START_MONTH = 4  # Indian financial year: April-March


def fiscal_year_for(d: date) -> str:
    """'2026-04-01' through '2027-03-31' -> '2026-27'."""
    start_year = d.year if d.month >= _FY_START_MONTH else d.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


async def allocate_doc_number(
    session: AsyncSession,
    *,
    doc_type: str,
    txn_date: date,
    prefix: str,
) -> str:
    """Allocate and return the next document number for (doc_type, fiscal
    year of txn_date), e.g. 'KJ/2026-27/0041'. Does not commit.
    """
    fy = fiscal_year_for(txn_date)

    locked = await session.execute(
        select(DocSequence.last_number)
        .where(DocSequence.doc_type == doc_type, DocSequence.fy == fy)
        .with_for_update()
    )
    last_number = locked.scalar_one_or_none()

    if last_number is None:
        # First number ever issued for this (doc_type, fy). Two concurrent
        # callers can both land here; ON CONFLICT DO NOTHING makes exactly
        # one INSERT win, and Postgres blocks the loser's statement until
        # the winner's transaction resolves, so the re-SELECT FOR UPDATE
        # below still serializes correctly either way.
        insert_stmt = pg_insert(DocSequence).values(doc_type=doc_type, fy=fy, prefix=prefix, last_number=0)
        insert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=["doc_type", "fy"])
        await session.execute(insert_stmt)

        locked = await session.execute(
            select(DocSequence.last_number)
            .where(DocSequence.doc_type == doc_type, DocSequence.fy == fy)
            .with_for_update()
        )
        last_number = locked.scalar_one()

    next_number = last_number + 1
    await session.execute(
        update(DocSequence)
        .where(DocSequence.doc_type == doc_type, DocSequence.fy == fy)
        .values(last_number=next_number)
    )
    await session.flush()

    return f"{prefix}{fy}/{next_number:04d}"
