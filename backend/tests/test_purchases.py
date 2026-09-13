"""Tests for /purchases — free-text lines, supplier-numbered bills, no
allocate_doc_number involved (that's the one real difference from sales)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import LedgerEntry
from app.services import ledger
from tests.conftest import auth_headers


def _purchase_body(party_id: int, *, bill_no="SUP-1001", quantity="10", rate="120.00", discount="0", date_="2026-04-05"):
    return {
        "party_id": party_id,
        "bill_no": bill_no,
        "bill_date": date_,
        "lines": [{"item_description": "Findings - hooks and jump rings", "quantity": quantity, "rate": rate}],
        "discount": discount,
    }


@pytest.mark.asyncio
async def test_create_purchase_computes_totals_and_posts_ledger(session, client, owner_user, supplier):
    resp = await client.post(
        "/purchases",
        json=_purchase_body(supplier.id, quantity="10", rate="120.00", discount="50.00"),
        headers=auth_headers(owner_user),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["bill_no"] == "SUP-1001"
    assert body["gross_amount"] == "1200.00"
    assert body["discount"] == "50.00"
    assert body["net_amount"] == "1150.00"
    assert len(body["lines"]) == 1
    assert body["lines"][0]["amount"] == "1200.00"

    bill_date = date.fromisoformat(body["bill_date"])
    report = await ledger.get_ledger(session, supplier.id, bill_date, bill_date)
    assert report.closing == Decimal("-1150.00")  # credit -> payable


@pytest.mark.asyncio
async def test_create_purchase_rejects_duplicate_bill_no_for_same_party(client, owner_user, supplier):
    first = await client.post("/purchases", json=_purchase_body(supplier.id, bill_no="DUPE-1"), headers=auth_headers(owner_user))
    assert first.status_code == 201

    second = await client.post("/purchases", json=_purchase_body(supplier.id, bill_no="DUPE-1"), headers=auth_headers(owner_user))
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_same_bill_no_allowed_for_different_parties(client, owner_user, supplier, party):
    first = await client.post("/purchases", json=_purchase_body(supplier.id, bill_no="SHARED-1"), headers=auth_headers(owner_user))
    second = await client.post("/purchases", json=_purchase_body(party.id, bill_no="SHARED-1"), headers=auth_headers(owner_user))

    assert first.status_code == 201
    assert second.status_code == 201


@pytest.mark.asyncio
async def test_edit_purchase_updates_ledger_row_not_a_second_one(session, client, owner_user, supplier):
    create = await client.post(
        "/purchases", json=_purchase_body(supplier.id, quantity="10", rate="120.00"), headers=auth_headers(owner_user)
    )
    purchase_id = create.json()["id"]

    edit = await client.patch(
        f"/purchases/{purchase_id}",
        json=_purchase_body(supplier.id, bill_no="SUP-1001", quantity="20", rate="120.00"),
        headers=auth_headers(owner_user),
    )
    assert edit.status_code == 200
    assert edit.json()["net_amount"] == "2400.00"

    rows = (
        (
            await session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.source_table == "purchases", LedgerEntry.source_id == purchase_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].credit == Decimal("2400.00")


@pytest.mark.asyncio
async def test_cancel_purchase_removes_ledger_row_and_keeps_document(session, client, owner_user, supplier):
    create = await client.post("/purchases", json=_purchase_body(supplier.id), headers=auth_headers(owner_user))
    purchase_id = create.json()["id"]

    resp = await client.post(
        f"/purchases/{purchase_id}/cancel", json={"reason": "wrong bill entered"}, headers=auth_headers(owner_user)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    rows = (
        (
            await session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.source_table == "purchases", LedgerEntry.source_id == purchase_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


@pytest.mark.asyncio
async def test_cancelled_purchase_rejects_further_edits_and_cancellation(client, owner_user, supplier):
    create = await client.post("/purchases", json=_purchase_body(supplier.id), headers=auth_headers(owner_user))
    purchase_id = create.json()["id"]

    await client.post(f"/purchases/{purchase_id}/cancel", json={"reason": "voided"}, headers=auth_headers(owner_user))

    edit = await client.patch(
        f"/purchases/{purchase_id}", json=_purchase_body(supplier.id, quantity="99"), headers=auth_headers(owner_user)
    )
    assert edit.status_code == 409

    recancel = await client.post(
        f"/purchases/{purchase_id}/cancel", json={"reason": "again"}, headers=auth_headers(owner_user)
    )
    assert recancel.status_code == 409


@pytest.mark.asyncio
async def test_staff_can_create_but_not_cancel_purchase(client, staff_user, owner_user, supplier):
    create = await client.post("/purchases", json=_purchase_body(supplier.id), headers=auth_headers(staff_user))
    assert create.status_code == 201
    purchase_id = create.json()["id"]

    cancel = await client.post(
        f"/purchases/{purchase_id}/cancel", json={"reason": "trying anyway"}, headers=auth_headers(staff_user)
    )
    assert cancel.status_code == 403
