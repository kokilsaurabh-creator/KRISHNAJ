"""Idempotent seeding of the 3 fixed accounts, read from Settings (.env or
real environment variables — same source as DATABASE_URL).

Run with: python -m app.seed

Idempotent means what it says: if a username already exists, it is left
completely alone — this never updates a password or role on a re-run, only
ever inserts users that are missing. Rotating a password is a job for
PATCH /users/{id}, not this script.
"""

import asyncio

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.db import SessionLocal
from app.models import User, UserRole


def _seed_accounts() -> list[tuple[str | None, str | None, UserRole, str]]:
    settings = get_settings()
    return [
        (settings.seed_admin_username, settings.seed_admin_password, UserRole.admin, "Admin"),
        (settings.seed_suresh_username, settings.seed_suresh_password, UserRole.owner, "Suresh"),
        (settings.seed_neena_username, settings.seed_neena_password, UserRole.staff, "Neena"),
    ]


async def seed() -> None:
    async with SessionLocal() as session:
        for username, password, role, display_name in _seed_accounts():
            if not username or not password:
                print(f"skipping {display_name}: username/password not set")
                continue

            existing = await session.execute(select(User.id).where(User.username == username))
            if existing.scalar_one_or_none() is not None:
                print(f"{username} already exists, skipping")
                continue

            session.add(
                User(
                    username=username,
                    display_name=display_name,
                    password_hash=hash_password(password),
                    role=role,
                )
            )
            print(f"seeded {username} ({role.value})")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
