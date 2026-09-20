"""Tests for /sales — the first real consumer of post_to_ledger,
repost_for_source, remove_for_source, and allocate_doc_number, exercised
end-to-end through the actual HTTP routes.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import DocStatus, LedgerEntry
from app.services import ledger
from tests.conftest import auth_headers


def _sale_body(party_id: int, product_id: int, *, quantity="2", rate="500.00", discount="0", date_="2026-04-05"):
    return {
        "party_id": party_id,
        "invoice_date": date_,
        "lines": [{"product_id": product_id, "quantity": quantity, "rate": rate}],
        "discount": discount,
    }


@pytest.mark.asyncio
async def test_create_sale_computes_totals_and_posts_ledger(session, client, owner_user, party, product):
    resp = await client.post(
        "/sales", json=_sale_body(party.id, product.id, quantity="3", rate="500.00", discount="100.00"),
        headers=auth_headers(owner_user),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["invoice_no"] == "1"
    assert body["gross_amount"] == "1500.00"
    assert body["discount"] == "100.00"
    assert body["net_amount"] == "1400.00"
    assert body["status"] == "active"
    assert len(body["lines"]) == 1
    assert body["lines"][0]["amount"] == "1500.00"

    invoice_date = date.fromisoformat(body["invoice_date"])
    report = await ledger.get_ledger(session, party.id, from_date=invoice_date, to_date=invoice_date)
    assert report.closing == Decimal("1400.00")


@pytest.mark.asyncio
async def test_create_sale_rejects_unknown_product(client, owner_user, party):
    resp = await client.post(
        "/sales", json=_sale_body(party.id, 999999),
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_sale_rejects_discount_exceeding_gross(client, owner_user, party, product):
    resp = await client.post(
        "/sales",
        json=_sale_body(party.id, product.id, quantity="1", rate="100.00", discount="500.00"),
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_sequential_sales_get_sequential_invoice_numbers(client, owner_user, party, product):
    first = await client.post("/sales", json=_sale_body(party.id, product.id), headers=auth_headers(owner_user))
    second = await client.post("/sales", json=_sale_body(party.id, product.id), headers=auth_headers(owner_user))

    assert first.json()["invoice_no"] == "1"
    assert second.json()["invoice_no"] == "2"


@pytest.mark.asyncio
async def test_edit_sale_updates_ledger_row_not_a_second_one(session, client, owner_user, party, product):
    create = await client.post(
        "/sales", json=_sale_body(party.id, product.id, quantity="2", rate="500.00"), headers=auth_headers(owner_user)
    )
    sale_id = create.json()["id"]
    invoice_no = create.json()["invoice_no"]

    edit = await client.patch(
        f"/sales/{sale_id}",
        json=_sale_body(party.id, product.id, quantity="4", rate="500.00"),
        headers=auth_headers(owner_user),
    )
    assert edit.status_code == 200
    body = edit.json()
    assert body["net_amount"] == "2000.00"
    assert body["invoice_no"] == invoice_no  # never reissued on edit

    rows = (
        (
            await session.execute(
                select(LedgerEntry).where(LedgerEntry.source_table == "sales", LedgerEntry.source_id == sale_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].debit == Decimal("2000.00")


@pytest.mark.asyncio
async def test_cancel_sale_removes_ledger_row_and_keeps_the_document(session, client, owner_user, party, product):
    create = await client.post("/sales", json=_sale_body(party.id, product.id), headers=auth_headers(owner_user))
    sale_id = create.json()["id"]

    resp = await client.post(
        f"/sales/{sale_id}/cancel", json={"reason": "customer returned goods"}, headers=auth_headers(owner_user)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "customer returned goods"
    assert body["cancelled_by"] == owner_user.id

    rows = (
        (
            await session.execute(
                select(LedgerEntry).where(LedgerEntry.source_table == "sales", LedgerEntry.source_id == sale_id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []

    # the document itself is untouched, just flagged
    still_there = await client.get(f"/sales/{sale_id}", headers=auth_headers(owner_user))
    assert still_there.status_code == 200
    assert still_there.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancelled_sale_rejects_further_edits(client, owner_user, party, product):
    create = await client.post("/sales", json=_sale_body(party.id, product.id), headers=auth_headers(owner_user))
    sale_id = create.json()["id"]

    await client.post(f"/sales/{sale_id}/cancel", json={"reason": "voided"}, headers=auth_headers(owner_user))

    edit = await client.patch(
        f"/sales/{sale_id}", json=_sale_body(party.id, product.id, quantity="9"), headers=auth_headers(owner_user)
    )
    assert edit.status_code == 409


@pytest.mark.asyncio
async def test_cancelled_sale_rejects_further_cancellation(client, owner_user, party, product):
    create = await client.post("/sales", json=_sale_body(party.id, product.id), headers=auth_headers(owner_user))
    sale_id = create.json()["id"]

    first_cancel = await client.post(
        f"/sales/{sale_id}/cancel", json={"reason": "voided"}, headers=auth_headers(owner_user)
    )
    assert first_cancel.status_code == 200

    second_cancel = await client.post(
        f"/sales/{sale_id}/cancel", json={"reason": "voided again"}, headers=auth_headers(owner_user)
    )
    assert second_cancel.status_code == 409


@pytest.mark.asyncio
async def test_staff_gets_403_cancelling_a_sale(client, staff_user, owner_user, party, product):
    create = await client.post("/sales", json=_sale_body(party.id, product.id), headers=auth_headers(owner_user))
    sale_id = create.json()["id"]

    resp = await client.post(
        f"/sales/{sale_id}/cancel", json={"reason": "trying anyway"}, headers=auth_headers(staff_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_staff_can_create_sales(client, staff_user, party, product):
    resp = await client.post("/sales", json=_sale_body(party.id, product.id), headers=auth_headers(staff_user))
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_owner_gets_200_cancelling_a_sale(client, owner_user, party, product):
    create = await client.post("/sales", json=_sale_body(party.id, product.id), headers=auth_headers(owner_user))
    sale_id = create.json()["id"]

    resp = await client.post(
        f"/sales/{sale_id}/cancel", json={"reason": "correcting entry"}, headers=auth_headers(owner_user)
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_sales_numbering_starts_at_set_number_then_locks(client, owner_user, admin_user, party, product):
    admin = auth_headers(admin_user)
    assert (await client.put("/sales/numbering", json={"start_number": 867}, headers=admin)).status_code == 200

    first = await client.post("/sales", json=_sale_body(party.id, product.id), headers=auth_headers(owner_user))
    second = await client.post("/sales", json=_sale_body(party.id, product.id), headers=auth_headers(owner_user))
    assert first.json()["invoice_no"] == "867"
    assert second.json()["invoice_no"] == "868"

    locked = await client.put("/sales/numbering", json={"start_number": 5000}, headers=admin)
    assert locked.status_code == 409
