"""Pydantic response schemas for health-check endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Schema for the GET /health response body.

    Attributes:
        status: Overall service health; either ``"healthy"`` or ``"unhealthy"``.
        database: Database connectivity state; either ``"connected"`` or
            ``"disconnected"``.
    """

    status: str
    database: str
