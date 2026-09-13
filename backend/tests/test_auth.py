"""Tests for /auth/login, /auth/me, /auth/change-password."""

import pytest

from app.core.security import hash_password
from app.models import User, UserRole
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_login_succeeds_with_correct_password(session, client):
    user = User(username="testowner", display_name="Test Owner", password_hash=hash_password("s3cret!"), role=UserRole.owner)
    session.add(user)
    await session.commit()

    resp = await client.post("/auth/login", data={"username": "testowner", "password": "s3cret!"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(session, client):
    user = User(username="testowner2", display_name="Test Owner", password_hash=hash_password("s3cret!"), role=UserRole.owner)
    session.add(user)
    await session.commit()

    resp = await client.post("/auth/login", data={"username": "testowner2", "password": "wrong"})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_inactive_user(session, client):
    user = User(
        username="deactivated",
        display_name="Deactivated",
        password_hash=hash_password("s3cret!"),
        role=UserRole.staff,
        is_active=False,
    )
    session.add(user)
    await session.commit()

    resp = await client.post("/auth/login", data={"username": "deactivated", "password": "s3cret!"})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client, owner_user):
    resp = await client.get("/auth/me", headers=auth_headers(owner_user))

    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "suresh"
    assert body["role"] == "owner"
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_missing_token_is_rejected(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_then_login_with_new_password(session, client):
    user = User(username="rotator", display_name="Rotator", password_hash=hash_password("old-pass"), role=UserRole.staff)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    resp = await client.post(
        "/auth/change-password",
        json={"old_password": "old-pass", "new_password": "new-pass"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 204

    old_login = await client.post("/auth/login", data={"username": "rotator", "password": "old-pass"})
    assert old_login.status_code == 401

    new_login = await client.post("/auth/login", data={"username": "rotator", "password": "new-pass"})
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_old_password(session, client):
    # Needs a real bcrypt hash (unlike the shared owner_user/staff_user/
    # admin_user fixtures, whose password_hash is a placeholder — fine for
    # tests that only need a valid JWT, wrong for anything that actually
    # calls verify_password against it, like this one).
    user = User(username="pwtest", display_name="PW Test", password_hash=hash_password("correct-pw"), role=UserRole.owner)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    resp = await client.post(
        "/auth/change-password",
        json={"old_password": "not-the-real-one", "new_password": "whatever"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 400
