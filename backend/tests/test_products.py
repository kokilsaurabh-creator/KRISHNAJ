"""Tests for /products — same require_role shape as /parties, kept brief
since the permission-matrix wiring is already exercised there."""

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_staff_gets_403_creating_a_product(client, staff_user):
    resp = await client.post(
        "/products",
        json={"code": "BNG-001", "name": "Gold Plated Bangle"},
        headers=auth_headers(staff_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_owner_gets_201_creating_a_product(client, owner_user):
    resp = await client.post(
        "/products",
        json={"code": "BNG-001", "name": "Gold Plated Bangle", "default_rate": "450.00"},
        headers=auth_headers(owner_user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "BNG-001"
    assert body["uom"] == "PCS"


@pytest.mark.asyncio
async def test_staff_can_list_products(client, staff_user, owner_user):
    create = await client.post(
        "/products",
        json={"code": "ER-001", "name": "Jhumka Earrings"},
        headers=auth_headers(owner_user),
    )
    assert create.status_code == 201

    resp = await client.get("/products", headers=auth_headers(staff_user))
    assert resp.status_code == 200
    assert any(row["code"] == "ER-001" for row in resp.json())
