"""Alembic migration environment.

Uses the application's existing async engine and declarative Base so that:
- The real DATABASE_URL (loaded via pydantic-settings from .env) is always used
- All ORM models registered on Base.metadata are introspected for autogenerate
- No second engine is created; the same connection pool is reused

The sys.path insertion below makes the ``app`` package importable when Alembic
is invoked from the project root without the src layout on PYTHONPATH, though
the recommended invocation is::

    PYTHONPATH=src poetry run alembic <command>
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy.engine import Connection

from alembic import context

# ---------------------------------------------------------------------------
# Ensure the src layout is importable.
#
# This guard means alembic/env.py works whether or not the caller has
# pre-populated PYTHONPATH.  The absolute path avoids any ambiguity
# introduced by the current working directory.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Import the shared engine and declarative base from the application.
# Importing app.models registers all ORM models on Base.metadata, which is
# required for autogenerate to detect tables correctly.
from app.core.database import Base, engine  # noqa: E402
import app.models  # noqa: E402, F401  — side-effect import to populate metadata

# ---------------------------------------------------------------------------
# Alembic Config
# ---------------------------------------------------------------------------
config = context.config

# Wire up the standard Python logging configuration defined in alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic at the project's declarative metadata so autogenerate can
# compare the current database schema against the ORM model definitions.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations without an active database connection.

    Generates SQL statements that can be reviewed and applied manually.
    The URL is taken from the ini file's ``sqlalchemy.url`` placeholder;
    for a real offline script, override it via ``--x`` options or by
    temporarily setting the value in alembic.ini.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode (async)
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    """Execute pending migrations against an open synchronous connection.

    Called by ``run_async_migrations`` via ``connection.run_sync`` so that
    the synchronous Alembic context API can operate inside an async engine
    connection.
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Acquire a connection from the application engine and apply migrations.

    Re-uses the module-level ``engine`` from ``app.core.database`` rather
    than constructing a second engine, so pool configuration and dialect
    settings remain consistent with the running application.
    """
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
