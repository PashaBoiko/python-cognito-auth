from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from app.core.config import redis_settings

# ---------------------------------------------------------------------------
# Module-level singleton
#
# A single Redis client instance is shared across all requests.  The
# redis-py async client manages an internal connection pool, so reusing one
# client is both safe and efficient — no per-request instantiation is needed.
#
# Typed as ``aioredis.Redis | None`` rather than initialised eagerly so that
# the connection is only established during the ASGI lifespan, not at import
# time.  This prevents test-time failures when Redis is unavailable and keeps
# startup failure signals explicit and observable.
# ---------------------------------------------------------------------------
redis_client: aioredis.Redis | None = None


async def init_redis() -> None:
    """Initialise the module-level Redis client singleton.

    Called once during application startup via the lifespan context manager.
    Uses ``decode_responses=True`` so that all values retrieved from Redis
    are returned as ``str`` rather than ``bytes``, matching the expected
    usage across token-storage helpers.
    """
    global redis_client

    redis_client = aioredis.from_url(
        redis_settings.REDIS_URL,
        decode_responses=True,
    )


async def close_redis() -> None:
    """Close the Redis client and release all pooled connections.

    Called once during application shutdown via the lifespan context manager.
    Guarded by a ``None`` check so that shutdown is safe even when
    ``init_redis`` was never reached (e.g. during error-path startup).
    """
    global redis_client

    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """ASGI lifespan context manager for Redis connection management.

    Registers Redis initialisation on startup and guaranteed teardown on
    shutdown.  Pass this function to the ``FastAPI`` constructor via the
    ``lifespan`` parameter:

    .. code-block:: python

        app = FastAPI(lifespan=lifespan)
    """
    await init_redis()
    try:
        yield
    finally:
        # ``finally`` ensures ``close_redis`` is called even when startup
        # raises after ``init_redis`` completes successfully.
        await close_redis()


async def get_redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency that yields the shared Redis client.

    Raises ``RuntimeError`` if called before the lifespan has initialised the
    client, providing a clear failure signal rather than a cryptic
    ``AttributeError`` on ``None``.

    Usage::

        @router.get("/example")
        async def example(redis: Annotated[aioredis.Redis, Depends(get_redis_client)]):
            value = await redis.get("some-key")
    """
    if redis_client is None:
        raise RuntimeError(
            "Redis client has not been initialised. "
            "Ensure the application lifespan has started before injecting the client."
        )
    yield redis_client
