"""Tests for /payments — direction picks both the doc_sequences series
(RCP/ vs PMT/) and the ledger sign, and can't be changed on edit."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import LedgerEntry
from app.services import ledger
from tests.conftest import auth_headers


def _payment_body(party_id: int, *, direction="in", amount="1000.00", mode="Cash", date_="2026-04-05"):
    return {
        "party_id": party_id,
        "payment_date": date_,
        "direction": direction,
        "amount": amount,
        "mode": mode,
    }


@pytest.mark.asyncio
async def test_receipt_credits_the_party_and_gets_rcp_prefix(session, client, owner_user, party):
    resp = await client.post(
        "/payments", json=_payment_body(party.id, direction="in", amount="1500.00"), headers=auth_headers(owner_user)
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["voucher_no"] == "RCP/2026-27/0001"
    assert body["direction"] == "in"

    payment_date = date.fromisoformat(body["payment_date"])
    report = await ledger.get_ledger(session, party.id, payment_date, payment_date)
    assert report.closing == Decimal("-1500.00")  # credit -> reduces what they owe


@pytest.mark.asyncio
async def test_payment_out_debits_the_party_and_gets_pmt_prefix(session, client, owner_user, supplier):
    resp = await client.post(
        "/payments",
        json=_payment_body(supplier.id, direction="out", amount="800.00"),
        headers=auth_headers(owner_user),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["voucher_no"] == "PMT/2026-27/0001"

    payment_date = date.fromisoformat(body["payment_date"])
    report = await ledger.get_ledger(session, supplier.id, payment_date, payment_date)
    assert report.closing == Decimal("800.00")  # debit -> reduces what we owe, shows as receivable-side movement


@pytest.mark.asyncio
async def test_receipts_and_payments_get_independent_sequences(client, owner_user, party, supplier):
    r1 = await client.post("/payments", json=_payment_body(party.id, direction="in"), headers=auth_headers(owner_user))
    p1 = await client.post("/payments", json=_payment_body(supplier.id, direction="out"), headers=auth_headers(owner_user))
    r2 = await client.post("/payments", json=_payment_body(party.id, direction="in"), headers=auth_headers(owner_user))

    assert r1.json()["voucher_no"] == "RCP/2026-27/0001"
    assert p1.json()["voucher_no"] == "PMT/2026-27/0001"
    assert r2.json()["voucher_no"] == "RCP/2026-27/0002"


@pytest.mark.asyncio
async def test_edit_payment_updates_ledger_row_not_a_second_one(session, client, owner_user, party):
    create = await client.post(
        "/payments", json=_payment_body(party.id, amount="1000.00"), headers=auth_headers(owner_user)
    )
    payment_id = create.json()["id"]

    edit = await client.patch(
        f"/payments/{payment_id}",
        json=_payment_body(party.id, amount="2500.00"),
        headers=auth_headers(owner_user),
    )
    assert edit.status_code == 200
    assert edit.json()["amount"] == "2500.00"
    assert edit.json()["voucher_no"] == create.json()["voucher_no"]

    rows = (
        (
            await session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.source_table == "payments", LedgerEntry.source_id == payment_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].credit == Decimal("2500.00")


@pytest.mark.asyncio
async def test_edit_payment_rejects_direction_change(client, owner_user, party):
    create = await client.post(
        "/payments", json=_payment_body(party.id, direction="in"), headers=auth_headers(owner_user)
    )
    payment_id = create.json()["id"]

    edit = await client.patch(
        f"/payments/{payment_id}",
        json=_payment_body(party.id, direction="out"),
        headers=auth_headers(owner_user),
    )
    assert edit.status_code == 400


@pytest.mark.asyncio
async def test_cancel_payment_removes_ledger_row_and_keeps_document(session, client, owner_user, party):
    create = await client.post("/payments", json=_payment_body(party.id), headers=auth_headers(owner_user))
    payment_id = create.json()["id"]

    resp = await client.post(
        f"/payments/{payment_id}/cancel", json={"reason": "wrong party"}, headers=auth_headers(owner_user)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    rows = (
        (
            await session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.source_table == "payments", LedgerEntry.source_id == payment_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


@pytest.mark.asyncio
async def test_cancelled_payment_rejects_further_edits_and_cancellation(client, owner_user, party):
    create = await client.post("/payments", json=_payment_body(party.id), headers=auth_headers(owner_user))
    payment_id = create.json()["id"]

    await client.post(f"/payments/{payment_id}/cancel", json={"reason": "voided"}, headers=auth_headers(owner_user))

    edit = await client.patch(
        f"/payments/{payment_id}", json=_payment_body(party.id, amount="1.00"), headers=auth_headers(owner_user)
    )
    assert edit.status_code == 409

    recancel = await client.post(
        f"/payments/{payment_id}/cancel", json={"reason": "again"}, headers=auth_headers(owner_user)
    )
    assert recancel.status_code == 409


@pytest.mark.asyncio
async def test_transfer_to_vendor_splits_ledger_and_cancel_restores_both(session, client, owner_user, party, supplier):
    body = _payment_body(party.id, direction="in", amount="100.00")
    body["transfer_to_party_id"] = supplier.id
    body["transfer_amount"] = "60.00"

    create = await client.post("/payments", json=body, headers=auth_headers(owner_user))
    assert create.status_code == 201
    payment_id = create.json()["id"]
    payment_date = date.fromisoformat(create.json()["payment_date"])

    customer_report = await ledger.get_ledger(session, party.id, payment_date, payment_date)
    assert customer_report.closing == Decimal("-100.00")  # full amount received, credit

    vendor_report = await ledger.get_ledger(session, supplier.id, payment_date, payment_date)
    assert vendor_report.closing == Decimal("60.00")  # transfer amount only, debit

    cancel = await client.post(
        f"/payments/{payment_id}/cancel", json={"reason": "test"}, headers=auth_headers(owner_user)
    )
    assert cancel.status_code == 200

    customer_after = await ledger.get_ledger(session, party.id, payment_date, payment_date)
    assert customer_after.closing == Decimal("0.00")

    vendor_after = await ledger.get_ledger(session, supplier.id, payment_date, payment_date)
    assert vendor_after.closing == Decimal("0.00")


@pytest.mark.asyncio
async def test_staff_gets_403_cancelling_a_payment(client, staff_user, owner_user, party):
    create = await client.post("/payments", json=_payment_body(party.id), headers=auth_headers(owner_user))
    payment_id = create.json()["id"]

    resp = await client.post(
        f"/payments/{payment_id}/cancel", json={"reason": "trying anyway"}, headers=auth_headers(staff_user)
    )
    assert resp.status_code == 403
