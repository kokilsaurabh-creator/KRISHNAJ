"""Tests for GET /ledger/{party_id} — the read endpoint behind the ledger
screen and its PDF export."""

from decimal import Decimal

import pytest

from tests.conftest import auth_headers


def _sale_body(party_id: int, product_id: int, *, quantity="2", rate="500.00", date_="2026-04-05"):
    return {
        "party_id": party_id,
        "invoice_date": date_,
        "lines": [{"product_id": product_id, "quantity": quantity, "rate": rate}],
        "discount": "0",
    }


@pytest.mark.asyncio
async def test_ledger_returns_opening_rows_totals_and_closing(client, owner_user, party, product, bank):
    headers = auth_headers(owner_user)

    await client.post(
        f"/parties/{party.id}/opening-balance",
        json={"as_of_date": "2026-04-01", "amount": "10000.00"},
        headers=headers,
    )
    await client.post(
        "/sales", json=_sale_body(party.id, product.id, quantity="3", rate="500.00", date_="2026-04-10"), headers=headers
    )
    await client.post(
        "/payments",
        json={
            "party_id": party.id,
            "payment_date": "2026-04-12",
            "direction": "in",
            "amount": "4000.00",
            "mode": "UPI",
            "bank_id": bank.id,
        },
        headers=headers,
    )

    resp = await client.get(f"/ledger/{party.id}", params={"from": "2026-04-02", "to": "2026-04-30"}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()

    assert body["party"]["id"] == party.id
    assert body["party"]["name"] == "Radha Bangles"
    assert body["opening"] == "10000.00"  # the opening-balance row, dated before the range
    assert body["total_debit"] == "1500.00"
    assert body["total_credit"] == "4000.00"
    assert body["closing"] == "7500.00"

    assert [r["type"] for r in body["rows"]] == ["sale", "receipt"]
    assert [r["balance"] for r in body["rows"]] == ["11500.00", "7500.00"]


@pytest.mark.asyncio
async def test_cancelled_sale_disappears_from_the_ledger(client, owner_user, party, product):
    headers = auth_headers(owner_user)

    create = await client.post("/sales", json=_sale_body(party.id, product.id), headers=headers)
    sale_id = create.json()["id"]

    before = await client.get(
        f"/ledger/{party.id}", params={"from": "2026-04-01", "to": "2026-04-30"}, headers=headers
    )
    assert len(before.json()["rows"]) == 1
    assert before.json()["closing"] == "1000.00"

    await client.post(f"/sales/{sale_id}/cancel", json={"reason": "returned"}, headers=headers)

    after = await client.get(
        f"/ledger/{party.id}", params={"from": "2026-04-01", "to": "2026-04-30"}, headers=headers
    )
    assert after.json()["rows"] == []
    assert after.json()["closing"] == "0.00"


@pytest.mark.asyncio
async def test_empty_range_still_reports_correct_opening(client, owner_user, party, product):
    headers = auth_headers(owner_user)

    await client.post(
        "/sales", json=_sale_body(party.id, product.id, quantity="2", rate="750.00", date_="2026-04-05"), headers=headers
    )

    resp = await client.get(f"/ledger/{party.id}", params={"from": "2026-06-01", "to": "2026-06-30"}, headers=headers)

    body = resp.json()
    assert body["rows"] == []
    assert body["opening"] == "1500.00"
    assert body["closing"] == "1500.00"
    assert body["total_debit"] == "0.00"
    assert body["total_credit"] == "0.00"


@pytest.mark.asyncio
async def test_amounts_serialise_as_strings_not_floats(client, owner_user, party, product):
    """The PDF and the screen must show identical figures; JSON floats
    would let 0.1+0.2 style drift in between."""
    headers = auth_headers(owner_user)
    await client.post(
        "/sales", json=_sale_body(party.id, product.id, quantity="3", rate="33.33", date_="2026-04-05"), headers=headers
    )

    resp = await client.get(f"/ledger/{party.id}", params={"from": "2026-04-01", "to": "2026-04-30"}, headers=headers)
    body = resp.json()

    assert isinstance(body["closing"], str)
    assert isinstance(body["rows"][0]["debit"], str)
    assert body["closing"] == "99.99"
    assert Decimal(body["closing"]) == Decimal("99.99")


@pytest.mark.asyncio
async def test_staff_can_read_the_ledger(client, staff_user, party):
    resp = await client.get(
        f"/ledger/{party.id}", params={"from": "2026-04-01", "to": "2026-04-30"}, headers=auth_headers(staff_user)
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unknown_party_is_404(client, owner_user):
    resp = await client.get(
        "/ledger/999999", params={"from": "2026-04-01", "to": "2026-04-30"}, headers=auth_headers(owner_user)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reversed_date_range_is_400(client, owner_user, party):
    resp = await client.get(
        f"/ledger/{party.id}", params={"from": "2026-04-30", "to": "2026-04-01"}, headers=auth_headers(owner_user)
    )
    assert resp.status_code == 400
