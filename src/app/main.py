from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Environment, app_settings
from app.core.redis import lifespan
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router


def create_app() -> FastAPI:
    openapi_url = (
        "/openapi.json" if app_settings.APP_ENV == Environment.DEVELOPMENT else None
    )

    app = FastAPI(
        title="Python Auth Microservice",
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

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
        return {"message": "Python Auth Microservice"}

    return app
