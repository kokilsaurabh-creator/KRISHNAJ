"""Test fixtures.

Tests run against a real Postgres database — set TEST_DATABASE_URL (or
DATABASE_URL) to a disposable database before running pytest. Native
Postgres enums and the partial unique index on ledger_entries are integral
to what's being tested, so sqlite is not an option here.

Tables are created straight from the SQLAlchemy metadata (Base.metadata),
not by running the Alembic migration, so these tests are fast and don't
need the alembic CLI available. That means they validate the ORM models +
ledger.py, not the migration file byte-for-byte — run `alembic upgrade
head` against a scratch database at least once to sanity-check the
migration itself.

The schema is (re)created once in pytest_configure, using its own throwaway
event loop via asyncio.run(), *before* pytest-asyncio's per-test event loop
exists. Every fixture below is function-scoped on top of that, which sidesteps
pytest-asyncio's event-loop-scope-mismatch footguns entirely instead of
juggling session-scoped async fixtures.
"""

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.core.security import create_access_token
from app.db import get_session, make_engine
from app.main import app
from app.models import Base, Party, PartyType, User, UserRole


def _test_db_url() -> str:
    settings = get_settings()
    return settings.test_database_url or settings.database_url


def pytest_configure(config) -> None:
    async def _setup() -> None:
        eng = make_engine(_test_db_url())
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

    asyncio.run(_setup())


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = make_engine(_test_db_url())
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s
        await s.rollback()

    # Isolate tests from each other: wipe every table, children before
    # parents so FKs don't block the delete.
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """An httpx client hitting the real FastAPI app in-process, with
    get_session overridden to hand out THIS test's session — so API calls
    and direct `session` fixture use in the same test share one transaction
    and roll back together.
    """

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_user(session: AsyncSession) -> User:
    user = User(username="admin", display_name="Admin", password_hash="not-a-real-hash", role=UserRole.admin)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def owner_user(session: AsyncSession) -> User:
    user = User(
        username="suresh",
        display_name="Suresh",
        password_hash="not-a-real-hash",
        role=UserRole.owner,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def staff_user(session: AsyncSession) -> User:
    user = User(username="neena", display_name="Neena", password_hash="not-a-real-hash", role=UserRole.staff)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def party(session: AsyncSession) -> Party:
    p = Party(party_type=PartyType.customer, name="Radha Bangles")
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


@pytest_asyncio.fixture
async def supplier(session: AsyncSession) -> Party:
    p = Party(party_type=PartyType.supplier, name="Meenakshi Findings Co")
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p
