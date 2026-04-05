import asyncio
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.redis import get_redis_client
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_DB_PROBE_TIMEOUT_SECONDS = 5


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Returns the overall service health, database connectivity status, and Redis "
        "connectivity status. Responds with HTTP 200 when both the database and Redis "
        "are reachable and HTTP 503 if either is unreachable."
    ),
)
async def health_check(
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> HealthResponse | JSONResponse:
    database_status = "connected"
    redis_status = "connected"

    try:
        await asyncio.wait_for(
            session.execute(text("SELECT 1")),
            timeout=_DB_PROBE_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception("Health check database probe failed")
        database_status = "disconnected"

    try:
        await asyncio.wait_for(
            redis_client.ping(),  # type: ignore[arg-type]
            timeout=_DB_PROBE_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception("Health check Redis probe failed")
        redis_status = "disconnected"

    overall_status = (
        "healthy"
        if database_status == "connected" and redis_status == "connected"
        else "unhealthy"
    )

    response_body = HealthResponse(
        status=overall_status,
        database=database_status,
        redis=redis_status,
    )

    if overall_status == "unhealthy":
        return JSONResponse(status_code=503, content=response_body.model_dump())

    return response_body
