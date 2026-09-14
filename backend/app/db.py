import ssl
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

try:
    import certifi

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # pragma: no cover - certifi ships transitively today
    _SSL_CONTEXT = ssl.create_default_context()


_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding"}


def to_asyncpg_url(raw_url: str) -> tuple[str, dict]:
    """Normalise a standard postgres:// URL (e.g. Neon's) for asyncpg.

    Neon connection strings come as
    `postgresql://...?sslmode=require&channel_binding=require`. asyncpg's
    URL/DSN parser doesn't recognise either of those (they're libpq/psycopg
    concepts — channel_binding in particular is a SCRAM extra that asyncpg
    doesn't negotiate at all), and raises on an unrecognised param if they're
    left in place. So we strip them and translate sslmode into connect_args
    instead; dropping channel_binding doesn't weaken the connection, TLS is
    still enforced via ssl=True, asyncpg just never attempts that extra
    SCRAM step.
    """
    parts = urlsplit(raw_url)
    scheme = "postgresql+asyncpg"

    all_params = dict(parse_qsl(parts.query))
    query_pairs = [(k, v) for k, v in parse_qsl(parts.query) if k not in _LIBPQ_ONLY_PARAMS]
    sslmode = all_params.get("sslmode")

    new_query = urlencode(query_pairs)
    normalised = urlunsplit((scheme, parts.netloc, parts.path, new_query, parts.fragment))

    connect_args: dict = {
        # Neon's connection string points at its "-pooler" endpoint, which
        # routes through PgBouncer in transaction-pooling mode: a different
        # physical Postgres connection can back each transaction. asyncpg's
        # default behaviour is to PREPARE and cache statements per
        # connection, which under that kind of pooling produces intermittent
        # "prepared statement does not exist" errors once traffic is
        # concurrent enough to actually rotate connections — this is a
        # documented asyncpg/PgBouncer incompatibility, not specific to us.
        # Disabling asyncpg's statement cache is the standard fix and costs
        # nothing meaningful at our query volume.
        "statement_cache_size": 0,
    }
    if sslmode in ("require", "verify-ca", "verify-full"):
        # Plain ssl=True hands asyncpg ssl.create_default_context(), which on
        # some Windows setups can't complete the chain from the OS trust
        # store alone ("unable to get local issuer certificate") even though
        # the server's chain is fine. Using certifi's bundle explicitly is
        # the standard fix and works the same on every platform.
        connect_args["ssl"] = _SSL_CONTEXT

    return normalised, connect_args


def make_engine(database_url: str):
    url, connect_args = to_asyncpg_url(database_url)
    settings = get_settings()
    return create_async_engine(
        url,
        echo=settings.sql_echo,
        connect_args=connect_args,
        # Sized for serverless, not for a long-running server: this engine
        # is one of potentially many independent instances (one per Vercel
        # function container), each importing this module exactly once at
        # cold start and reusing the resulting pool across every warm
        # invocation that container handles. SQLAlchemy's own defaults
        # (pool_size=5, max_overflow=10) assume ONE process serving all
        # traffic — under serverless that same default multiplied across
        # N concurrently-scaled containers is how you exhaust Neon's
        # connection limit under a burst. A small pool per container is
        # fine because Neon's pooler endpoint (the "-pooler" in the
        # hostname) is itself already multiplexing these down to a much
        # smaller number of real backend connections.
        pool_size=1,
        max_overflow=2,
        # A container can be frozen between invocations; the TCP socket can
        # die during that freeze even though the process (and this pool)
        # survives. pre_ping validates a connection with a cheap round trip
        # before handing it out, transparently reconnecting if it's dead,
        # rather than surfacing a broken-connection error on the request
        # that happens to draw the stale one.
        pool_pre_ping=True,
    )


_settings = get_settings()
engine = make_engine(_settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
