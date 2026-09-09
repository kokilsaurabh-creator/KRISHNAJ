from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Neon Postgres connection string, e.g.
    # postgresql://user:pass@host/dbname?sslmode=require
    database_url: str = "postgresql://postgres:postgres@localhost:5432/krishnaj"

    # Separate database used by the pytest suite. Defaults to database_url
    # with the database name swapped for one ending in _test, but you should
    # point this at a real, disposable Postgres database (a local instance
    # or a throwaway Neon branch) via the environment.
    test_database_url: str | None = None

    sql_echo: bool = False

    jwt_secret: str = "change-me-in-env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12


@lru_cache
def get_settings() -> Settings:
    return Settings()
