"""Application factory module for the Python Auth Microservice.

This module exposes a ``create_app`` factory function that is consumed by
uvicorn via its ``--factory`` flag::

    uvicorn app.main:create_app --factory

Later slices will extend the factory with router mounting and additional
middleware as requirements grow.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Environment, app_settings
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router


def create_app() -> FastAPI:
    """Construct and return the FastAPI application instance.

    OpenAPI docs are hidden in non-development environments to avoid
    leaking schema information to external consumers.  CORS is configured
    from the module-level ``app_settings`` singleton so that the server
    refuses to start if ``ALLOWED_ORIGINS`` is absent.

    Returns:
        FastAPI: Configured application instance ready for ASGI serving.
    """
    openapi_url = (
        "/openapi.json" if app_settings.APP_ENV == Environment.DEVELOPMENT else None
    )

    app = FastAPI(title="Python Auth Microservice", openapi_url=openapi_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.ALLOWED_ORIGINS,
        allow_methods=app_settings.ALLOWED_METHODS,
        allow_headers=["*"],
        allow_credentials=True,
    )

    app.include_router(health_router)

    app.include_router(auth_router, prefix="/api/v1")

    # Future API v1 routers
    # app.include_router(users_router, prefix="/api/v1")
    # app.include_router(roles_router, prefix="/api/v1")

    @app.get("/", summary="Health probe")
    async def root() -> dict[str, str]:
        """Return a minimal liveness response.

        This route is intentionally thin — it exists only so the service is
        immediately testable after scaffolding.  It will be replaced or
        augmented by a dedicated health-check router in a later slice.
        """
        return {"message": "Python Auth Microservice"}

    return app
