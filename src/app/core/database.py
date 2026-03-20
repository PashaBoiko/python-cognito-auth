from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import db_settings

# ---------------------------------------------------------------------------
# Naming convention
#
# Explicit names for all constraints and indexes allow Alembic to generate
# deterministic, readable migration scripts across databases and schema
# comparisons.  Without this, SQLAlchemy auto-generates names that differ
# between runs, causing Alembic to emit spurious DROP/CREATE statements.
# ---------------------------------------------------------------------------
POSTGRES_INDEXES_NAMING_CONVENTION: dict[str, str] = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)


# ---------------------------------------------------------------------------
# Async engine
#
# Pydantic's PostgresDsn serialises to ``postgresql://…``.  asyncpg requires
# the ``postgresql+asyncpg://`` dialect prefix, so the scheme is substituted
# before the URL is handed to SQLAlchemy.
#
# Pool sizing rationale:
#   pool_size=10    — keep up to 10 connections open between requests
#   max_overflow=20 — allow up to 20 additional connections under peak load
#   pool_pre_ping   — verify a connection is alive before returning it from
#                     the pool, preventing errors on stale/recycled connections
# ---------------------------------------------------------------------------
_raw_url: str = str(db_settings.DATABASE_URL).replace(
    "postgresql://", "postgresql+asyncpg://", 1
)

engine = create_async_engine(
    _raw_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

# ---------------------------------------------------------------------------
# Session factory
#
# ``expire_on_commit=False`` prevents SQLAlchemy from expiring ORM attributes
# after a commit.  In an async context, accessing an expired attribute would
# trigger an implicit lazy-load which is not supported by asyncpg, causing a
# ``MissingGreenlet`` error.
# ---------------------------------------------------------------------------
async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
