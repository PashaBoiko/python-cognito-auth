import asyncio
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_DB_PROBE_TIMEOUT_SECONDS = 5


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Returns the overall service health and database connectivity status. "
        "Responds with HTTP 200 when the database is reachable and HTTP 503 otherwise."
    ),
)
async def health_check(
    session: AsyncSession = Depends(get_db_session),
) -> HealthResponse | JSONResponse:
    try:
        await asyncio.wait_for(
            session.execute(text("SELECT 1")),
            timeout=_DB_PROBE_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception("Health check database probe failed")
        return JSONResponse(
            status_code=503,
            content=HealthResponse(
                status="unhealthy",
                database="disconnected",
            ).model_dump(),
        )

    return HealthResponse(status="healthy", database="connected")
