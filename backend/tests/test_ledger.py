"""Tests for app/services/ledger.py.

Two tests from the original list aren't here yet, on purpose:

- "a cancelled sale rejects further edits/cancellation" — that rule belongs
  to the future sales route/service (it has to know a sale's status before
  deciding whether to call repost_for_source/remove_for_source at all).
  ledger.py itself is deliberately dumb about document status.
- "staff gets 403, owner gets 200" — needs the auth layer and real routes,
  neither of which exist yet.

Both land once the route layer is built on top of this.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import DocStatus, LedgerEntry, LedgerTxnType, PartyType, PaymentDirection
from app.services import ledger
from tests.helpers import create_payment, create_purchase, create_sale


@pytest.mark.asyncio
async def test_opening_plus_movement_equals_closing_for_any_range(session, party, owner_user):
    # Opening balance dated before every other entry.
    await ledger.post_to_ledger(
        session,
        party_id=party.id,
        txn_date=date(2026, 4, 1),
        txn_type=LedgerTxnType.opening,
        source_table=None,
        source_id=None,
        doc_no=None,
        debit=Decimal("10000.00"),
        credit=Decimal("0"),
        narration="opening balance",
    )
    await session.commit()

    await create_sale(
        session, party=party, user=owner_user, invoice_no="KJ/1", amount=Decimal("5000.00"), txn_date=date(2026, 4, 5)
    )
    await create_sale(
        session, party=party, user=owner_user, invoice_no="KJ/2", amount=Decimal("3000.00"), txn_date=date(2026, 4, 10)
    )
    await create_payment(
        session,
        party=party,
        user=owner_user,
        voucher_no="RCP/1",
        amount=Decimal("4000.00"),
        direction=PaymentDirection.IN,
        txn_date=date(2026, 4, 12),
    )
    await create_purchase(
        session, party=party, user=owner_user, bill_no="SUP/1", amount=Decimal("2000.00"), txn_date=date(2026, 4, 15)
    )
    await create_payment(
        session,
        party=party,
        user=owner_user,
        voucher_no="PMT/1",
        amount=Decimal("1000.00"),
        direction=PaymentDirection.OUT,
        txn_date=date(2026, 4, 20),
    )

    # A range that starts after the opening row but covers everything else.
    narrow = await ledger.get_ledger(session, party.id, date(2026, 4, 2), date(2026, 4, 30))
    assert narrow.opening == Decimal("10000.00")
    assert narrow.opening + (narrow.total_debit - narrow.total_credit) == narrow.closing
    assert narrow.closing == Decimal("13000.00")

    # A wide range that also swallows the opening row as an ordinary entry —
    # closing must land in the same place regardless of where the range starts.
    wide = await ledger.get_ledger(session, party.id, date(2026, 1, 1), date(2026, 12, 31))
    assert wide.opening == Decimal("0.00")
    assert wide.opening + (wide.total_debit - wide.total_credit) == wide.closing
    assert wide.closing == narrow.closing


@pytest.mark.asyncio
async def test_duplicate_source_posting_raises(session, party):
    kwargs = dict(
        party_id=party.id,
        txn_date=date(2026, 4, 5),
        txn_type=LedgerTxnType.sale,
        source_table="sales",
        source_id=999,
        doc_no="KJ/999",
        debit=Decimal("1000.00"),
        credit=Decimal("0"),
    )
    await ledger.post_to_ledger(session, **kwargs)
    await session.commit()

    with pytest.raises(ledger.DuplicatePostingError):
        await ledger.post_to_ledger(session, **kwargs)

    rows = (
        await session.execute(
            select(LedgerEntry).where(LedgerEntry.source_table == "sales", LedgerEntry.source_id == 999)
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_editing_a_sale_updates_ledger_row_not_a_second_one(session, party, owner_user):
    sale = await create_sale(
        session, party=party, user=owner_user, invoice_no="KJ/10", amount=Decimal("5000.00"), txn_date=date(2026, 4, 5)
    )

    await ledger.repost_for_source(
        session,
        source_table="sales",
        source_id=sale.id,
        party_id=party.id,
        txn_date=sale.invoice_date,
        txn_type=LedgerTxnType.sale,
        doc_no=sale.invoice_no,
        debit=Decimal("7500.00"),
        credit=Decimal("0"),
        narration="corrected amount",
    )
    await session.commit()

    rows = (
        await session.execute(
            select(LedgerEntry).where(LedgerEntry.source_table == "sales", LedgerEntry.source_id == sale.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].debit == Decimal("7500.00")

    report = await ledger.get_ledger(session, party.id, date(2026, 1, 1), date(2026, 12, 31))
    assert report.closing == Decimal("7500.00")


@pytest.mark.asyncio
async def test_cancelling_a_sale_removes_ledger_row_and_restores_balance(session, party, owner_user):
    before = await ledger.get_ledger(session, party.id, date(2026, 1, 1), date(2026, 12, 31))
    prior_closing = before.closing

    sale = await create_sale(
        session, party=party, user=owner_user, invoice_no="KJ/20", amount=Decimal("2500.00"), txn_date=date(2026, 4, 5)
    )

    removed = await ledger.remove_for_source(session, source_table="sales", source_id=sale.id)
    assert removed == 1

    sale.status = DocStatus.cancelled
    sale.cancelled_by = owner_user.id
    sale.cancel_reason = "test cancel"
    await session.commit()
    await session.refresh(sale)

    assert sale.status == DocStatus.cancelled

    rows = (
        await session.execute(
            select(LedgerEntry).where(LedgerEntry.source_table == "sales", LedgerEntry.source_id == sale.id)
        )
    ).scalars().all()
    assert rows == []

    after = await ledger.get_ledger(session, party.id, date(2026, 1, 1), date(2026, 12, 31))
    assert after.closing == prior_closing


@pytest.mark.asyncio
async def test_range_after_all_transactions_returns_full_opening_and_no_rows(session, party, owner_user):
    await create_sale(
        session, party=party, user=owner_user, invoice_no="KJ/30", amount=Decimal("1500.00"), txn_date=date(2026, 4, 5)
    )
    await create_payment(
        session,
        party=party,
        user=owner_user,
        voucher_no="RCP/30",
        amount=Decimal("500.00"),
        direction=PaymentDirection.IN,
        txn_date=date(2026, 4, 6),
    )

    report = await ledger.get_ledger(session, party.id, date(2026, 6, 1), date(2026, 6, 30))
    assert report.rows == []
    assert report.opening == Decimal("1000.00")
    assert report.closing == Decimal("1000.00")
    assert report.total_debit == Decimal("0.00")
    assert report.total_credit == Decimal("0.00")


@pytest.mark.asyncio
async def test_float_amounts_are_rejected(session, party):
    with pytest.raises(TypeError):
        await ledger.post_to_ledger(
            session,
            party_id=party.id,
            txn_date=date(2026, 4, 5),
            txn_type=LedgerTxnType.sale,
            source_table="sales",
            source_id=1234,
            doc_no="KJ/1234",
            debit=1000.0,  # float, not Decimal — must be rejected
            credit=Decimal("0"),
        )


@pytest.mark.asyncio
async def test_two_sided_entry_is_rejected(session, party):
    with pytest.raises(ledger.InvalidLedgerAmountError):
        await ledger.post_to_ledger(
            session,
            party_id=party.id,
            txn_date=date(2026, 4, 5),
            txn_type=LedgerTxnType.sale,
            source_table="sales",
            source_id=1235,
            doc_no="KJ/1235",
            debit=Decimal("100.00"),
            credit=Decimal("50.00"),
        )


@pytest.mark.asyncio
async def test_get_outstanding_includes_both_typed_parties_in_customer_report(session, party, supplier, owner_user):
    await create_sale(
        session, party=party, user=owner_user, invoice_no="KJ/40", amount=Decimal("1200.00"), txn_date=date(2026, 4, 5)
    )
    await create_purchase(
        session, party=supplier, user=owner_user, bill_no="SUP/40", amount=Decimal("800.00"), txn_date=date(2026, 4, 6)
    )

    customer_report = await ledger.get_outstanding(session, PartyType.customer, date(2026, 12, 31))
    by_id = {row.party_id: row for row in customer_report}
    assert by_id[party.id].balance == Decimal("1200.00")
    assert supplier.id not in by_id

    supplier_report = await ledger.get_outstanding(session, PartyType.supplier, date(2026, 12, 31))
    by_id = {row.party_id: row for row in supplier_report}
    assert by_id[supplier.id].balance == Decimal("-800.00")
