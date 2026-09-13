"""Idempotent seeding of the 3 fixed accounts from env vars.

Run with: python -m app.seed

Idempotent means what it says: if a username already exists, it is left
completely alone — this never updates a password or role on a re-run, only
ever inserts users that are missing. Rotating a password is a job for
PATCH /users/{id}, not this script.
"""

import asyncio
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db import SessionLocal
from app.models import User, UserRole

_SEED_ACCOUNTS = [
    ("SEED_ADMIN_USERNAME", "SEED_ADMIN_PASSWORD", UserRole.admin, "Admin"),
    ("SEED_SURESH_USERNAME", "SEED_SURESH_PASSWORD", UserRole.owner, "Suresh"),
    ("SEED_NEENA_USERNAME", "SEED_NEENA_PASSWORD", UserRole.staff, "Neena"),
]


async def seed() -> None:
    async with SessionLocal() as session:
        for username_var, password_var, role, display_name in _SEED_ACCOUNTS:
            username = os.environ.get(username_var)
            password = os.environ.get(password_var)
            if not username or not password:
                print(f"skipping {username_var}: {username_var}/{password_var} not set")
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
