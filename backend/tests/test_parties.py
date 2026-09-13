"""Tests for /parties, including the permission-matrix cases the ledger.py
review round deferred: staff 403 on create and opening-balance, owner 200
on both.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import LedgerEntry, LedgerTxnType
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_staff_gets_403_creating_a_party(client, staff_user):
    resp = await client.post(
        "/parties",
        json={"party_type": "customer", "name": "Should Not Be Created"},
        headers=auth_headers(staff_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_owner_gets_200_creating_a_party(client, owner_user):
    resp = await client.post(
        "/parties",
        json={"party_type": "customer", "name": "Radha Bangles"},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Radha Bangles"


@pytest.mark.asyncio
async def test_admin_gets_200_creating_a_party(client, admin_user):
    resp = await client.post(
        "/parties",
        json={"party_type": "supplier", "name": "Meenakshi Findings"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_staff_can_list_and_view_parties(client, staff_user, party):
    resp = await client.get("/parties", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    assert any(row["id"] == party.id for row in resp.json())

    resp = await client.get(f"/parties/{party.id}", headers=auth_headers(staff_user))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_staff_gets_403_setting_opening_balance(client, staff_user, party):
    resp = await client.post(
        f"/parties/{party.id}/opening-balance",
        json={"as_of_date": "2026-04-01", "amount": "5000.00"},
        headers=auth_headers(staff_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_owner_gets_200_setting_opening_balance(client, owner_user, party):
    resp = await client.post(
        f"/parties/{party.id}/opening-balance",
        json={"as_of_date": "2026-04-01", "amount": "5000.00"},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 200
    assert resp.json()["balance"] == "5000.00"


@pytest.mark.asyncio
async def test_opening_balance_is_idempotent(session, client, owner_user, party):
    headers = auth_headers(owner_user)
    first = await client.post(
        f"/parties/{party.id}/opening-balance",
        json={"as_of_date": "2026-04-01", "amount": "5000.00"},
        headers=headers,
    )
    assert first.status_code == 200

    second = await client.post(
        f"/parties/{party.id}/opening-balance",
        json={"as_of_date": "2026-04-01", "amount": "7000.00"},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["balance"] == "7000.00"

    rows = (
        (
            await session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.party_id == party.id,
                    LedgerEntry.txn_type == LedgerTxnType.opening,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].debit == Decimal("7000.00")


@pytest.mark.asyncio
async def test_staff_gets_403_updating_a_party(client, staff_user, party):
    resp = await client.patch(
        f"/parties/{party.id}",
        json={"notes": "staff shouldn't be able to do this"},
        headers=auth_headers(staff_user),
    )
    assert resp.status_code == 403
