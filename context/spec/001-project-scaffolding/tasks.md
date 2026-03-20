# Tasks: Project Scaffolding

**Spec:** `context/spec/001-project-scaffolding/`
**Prerequisites:** A local PostgreSQL instance must be running and accessible via the `DATABASE_URL` in `.env`. If PostgreSQL is not available locally, use Docker: `docker run -d --name pg-auth -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16`.

---

## Slice 1: Minimal Runnable FastAPI Application

_After this slice: the app starts with `uvicorn`, returns a response, and the project structure is in place._

- [x] **Slice 1: Minimal Runnable FastAPI Application**
  - [x] Initialize Poetry project with `pyproject.toml`: set Python `>=3.11,<4.0`, add core dependencies (`fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`), database deps (`sqlalchemy[asyncio]`, `asyncpg`, `alembic`), AWS deps (`boto3`), auth deps (`python-jose[cryptography]`), logging deps (`structlog`), and dev deps (`pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`). Create `.python-version` file with `3.11`. **[Agent: python-backend]**
  - [x] Create `src/app/` package with `__init__.py` and all sub-packages: `routers/`, `services/`, `repositories/`, `models/`, `schemas/`, `core/` — each with `__init__.py`. **[Agent: python-backend]**
  - [x] Create `app/main.py` with a `create_app() -> FastAPI` factory function. Mount a temporary root route returning `{"message": "Python Auth Microservice"}` so the app is immediately testable. **[Agent: python-backend]**
  - [x] Create `tests/__init__.py` and `tests/conftest.py` (empty for now). **[Agent: python-backend]**
  - [x] Create `.gitignore` with standard Python ignores (`.venv/`, `__pycache__/`, `.env`, `*.pyc`, `.mypy_cache/`, `.ruff_cache/`). **[Agent: python-backend]**
  - [x] **Verify:** Run `poetry install`, then `poetry run uvicorn app.main:app --factory --host 0.0.0.0 --port 8000`. Confirm the app starts and `curl http://localhost:8000/` returns a JSON response. **[Agent: python-backend]**

---

## Slice 2: Environment Configuration & CORS

_After this slice: the app loads all settings from `.env`, fails fast on missing required vars, and has CORS configured._

- [x] **Slice 2: Environment Configuration & CORS**
  - [x] Create `app/core/config.py` with three Pydantic Settings classes: `AppSettings` (APP_ENV enum, APP_HOST, APP_PORT, DEBUG, LOG_LEVEL, ALLOWED_ORIGINS, ALLOWED_METHODS with defaults), `DatabaseSettings` (DATABASE_URL as PostgresDsn, required), `CognitoSettings` (COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, COGNITO_REGION, all required). All classes use `SettingsConfigDict(env_file=".env")`. Instantiate module-level singletons. **[Agent: python-backend]**
  - [x] Create `.env.example` documenting all environment variables with placeholder values. Create a `.env` file (gitignored) with development defaults for local use. **[Agent: python-backend]**
  - [x] Update `app/main.py`: import settings, configure CORS middleware using `ALLOWED_ORIGINS` and `ALLOWED_METHODS`, conditionally set `openapi_url=None` when `APP_ENV` is not `development`. **[Agent: python-backend]**
  - [x] **Verify:** Run the app with a valid `.env` — confirm it starts successfully with CORS headers in responses. Then remove a required var (e.g., `DATABASE_URL`) from `.env` and confirm the app fails to start with a clear `ValidationError`. **[Agent: python-backend]**

---

## Slice 3: Database Engine & Dependency Injection

_After this slice: the SQLAlchemy async engine connects to PostgreSQL, and the session is injectable via `Depends()`._

- [x] **Slice 3: Database Engine & Dependency Injection**
  - [x] Create `app/core/database.py`: define `Base` (DeclarativeBase with naming conventions for pk, fk, uq, ix), create async engine from `DATABASE_URL` with `postgresql+asyncpg://` scheme conversion, `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`. Create `async_sessionmaker` with `expire_on_commit=False`. **[Agent: postgres-database]**
  - [x] Create `app/core/dependencies.py`: implement `get_db_session()` async generator yielding `AsyncSession` from the session maker. **[Agent: postgres-database]**
  - [x] **Verify:** With a running PostgreSQL instance, start the app and confirm it boots without database connection errors in the logs. Confirm the engine is created and the session dependency is importable. **[Agent: postgres-database]**

---

## Slice 4: Health Check Endpoint with DB Verification

_After this slice: `GET /health` returns database connectivity status — the full scaffolding spec is complete._

- [x] **Slice 4: Health Check Endpoint with DB Verification**
  - [x] Create `app/schemas/health.py`: define `HealthResponse` Pydantic model with `status: str` and `database: str`. **[Agent: python-backend]**
  - [x] Create `app/routers/health.py`: implement `GET /health` endpoint that injects `AsyncSession` via `Depends(get_db_session)`, executes `SELECT 1` with a 5-second timeout, returns `200 {"status": "healthy", "database": "connected"}` on success, or `503 {"status": "unhealthy", "database": "disconnected"}` on failure. **[Agent: python-backend]**
  - [x] Update `app/main.py`: mount the health router directly (no `/api/v1` prefix). Add a placeholder `/api/v1` prefix comment/router include for future endpoints. **[Agent: python-backend]**
  - [x] **Verify:** With PostgreSQL running, `curl http://localhost:8000/health` returns `200` with `{"status": "healthy", "database": "connected"}`. Stop PostgreSQL, repeat the curl — confirm `503` with `{"status": "unhealthy", "database": "disconnected"}`. Confirm response time is under 5 seconds in both cases. **[Agent: python-backend]**
