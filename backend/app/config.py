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

    # Comma-separated origins the browser is allowed to call this API from.
    # Only matters for cross-origin setups (local dev: Vite on :5173 calling
    # uvicorn on :8000). Under the single-domain Vercel deployment the
    # frontend and /api are same-origin, so the browser never sends a CORS
    # preflight and this is never consulted — nothing to set there.
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # Seed accounts for `python -m app.seed`, run by hand against whichever
    # DATABASE_URL is active — never part of a deploy. Read via Settings
    # (not raw os.environ) so the same .env that already has DATABASE_URL
    # is the only thing you need: no extra shell exports to remember before
    # running the script.
    seed_admin_username: str | None = None
    seed_admin_password: str | None = None
    seed_suresh_username: str | None = None
    seed_suresh_password: str | None = None
    seed_neena_username: str | None = None
    seed_neena_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
