"""Tests for app/services/doc_numbering.py."""

import asyncio
from datetime import date

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import DocSequence
from app.services.doc_numbering import allocate_doc_number, fiscal_year_for


def test_fiscal_year_spans_april_to_march():
    assert fiscal_year_for(date(2026, 4, 1)) == "2026-27"
    assert fiscal_year_for(date(2026, 9, 9)) == "2026-27"
    assert fiscal_year_for(date(2027, 3, 31)) == "2026-27"
    assert fiscal_year_for(date(2027, 4, 1)) == "2027-28"
    assert fiscal_year_for(date(2026, 3, 31)) == "2025-26"


@pytest.mark.asyncio
async def test_sequential_allocation_increments_and_formats(session):
    first = await allocate_doc_number(session, doc_type="sale", txn_date=date(2026, 4, 5), prefix="KJ/")
    second = await allocate_doc_number(session, doc_type="sale", txn_date=date(2026, 5, 1), prefix="KJ/")
    await session.commit()

    assert first == "KJ/2026-27/0001"
    assert second == "KJ/2026-27/0002"


@pytest.mark.asyncio
async def test_different_fiscal_years_get_independent_sequences(session):
    this_fy = await allocate_doc_number(session, doc_type="sale", txn_date=date(2026, 4, 5), prefix="KJ/")
    next_fy = await allocate_doc_number(session, doc_type="sale", txn_date=date(2027, 4, 5), prefix="KJ/")
    await session.commit()

    assert this_fy == "KJ/2026-27/0001"
    assert next_fy == "KJ/2027-28/0001"


@pytest.mark.asyncio
async def test_different_doc_types_get_independent_sequences(session):
    sale_no = await allocate_doc_number(session, doc_type="sale", txn_date=date(2026, 4, 5), prefix="KJ/")
    receipt_no = await allocate_doc_number(session, doc_type="receipt", txn_date=date(2026, 4, 5), prefix="RCP/")
    await session.commit()

    assert sale_no == "KJ/2026-27/0001"
    assert receipt_no == "RCP/2026-27/0001"


@pytest.mark.asyncio
async def test_concurrent_allocation_yields_distinct_numbers(engine):
    """This one deliberately bypasses the `session` fixture. The whole point
    is two REAL, independent transactions racing for the same
    doc_sequences row — under the savepoint-per-test isolation every other
    test uses, both allocations would happen on the same connection/
    transaction and couldn't actually block each other, which would prove
    nothing about the row lock. So this test opens two genuine connections,
    lets them race via asyncio.gather, and cleans up its own committed rows
    afterward instead of relying on rollback.
    """
    doc_type = "concurrency_test"
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def cleanup() -> None:
        async with session_factory() as s:
            await s.execute(delete(DocSequence).where(DocSequence.doc_type == doc_type))
            await s.commit()

    await cleanup()  # in case a previous interrupted run left rows behind
    try:

        async def allocate() -> str:
            async with session_factory() as s:
                number = await allocate_doc_number(
                    s, doc_type=doc_type, txn_date=date(2026, 4, 5), prefix="CT/"
                )
                await s.commit()
                return number

        first, second = await asyncio.gather(allocate(), allocate())

        assert first != second
        assert {first, second} == {"CT/2026-27/0001", "CT/2026-27/0002"}
    finally:
        await cleanup()
