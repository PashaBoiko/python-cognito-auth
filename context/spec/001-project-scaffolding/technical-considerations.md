# Technical Specification: Project Scaffolding

- **Functional Specification:** `context/spec/001-project-scaffolding/functional-spec.md`
- **Status:** Completed
- **Author(s):** Poe

---

## 1. High-Level Technical Approach

Bootstrap the auth microservice as a `src/`-layout Python package with FastAPI. Establish the 4-layer architecture (routers → services → repositories → models) plus supporting `schemas/` and `core/` packages. Configure Pydantic Settings for environment management, set up the SQLAlchemy async engine with asyncpg, wire FastAPI `Depends()` for dependency injection, and expose a `GET /health` endpoint with database connectivity verification. Use Poetry for dependency management.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1. Project Structure

```
python-auth/
├── src/
│   └── app/
│       ├── __init__.py
│       ├── main.py                  # FastAPI app factory, middleware, router mounting
│       ├── routers/
│       │   ├── __init__.py
│       │   └── health.py            # GET /health endpoint
│       ├── services/
│       │   └── __init__.py
│       ├── repositories/
│       │   └── __init__.py
│       ├── models/
│       │   └── __init__.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── health.py            # HealthResponse schema
│       └── core/
│           ├── __init__.py
│           ├── config.py            # Pydantic Settings classes
│           ├── database.py          # Async engine, session factory, Base
│           └── dependencies.py      # Depends() providers
├── tests/
│   ├── __init__.py
│   └── conftest.py
├── pyproject.toml
├── poetry.lock
├── .env.example
├── .python-version
└── .gitignore
```

### 2.2. Dependencies (`pyproject.toml`)

| Category | Packages |
|---|---|
| **Core** | `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings` |
| **Database** | `sqlalchemy[asyncio]`, `asyncpg`, `alembic` |
| **AWS** | `boto3` |
| **Auth** | `python-jose[cryptography]` |
| **Logging** | `structlog` |
| **Dev** | `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy` |

- Python version: `>=3.11,<4.0`
- `.python-version`: `3.11`

### 2.3. Environment Configuration (`app/core/config.py`)

Three Pydantic Settings classes, split by concern:

| Class | Fields | Defaults |
|---|---|---|
| `AppSettings` | `APP_ENV` (enum: development/staging/production), `APP_HOST`, `APP_PORT`, `DEBUG`, `LOG_LEVEL`, `ALLOWED_ORIGINS` (list[str]), `ALLOWED_METHODS` (list[str]) | `APP_ENV=production`, `APP_HOST=0.0.0.0`, `APP_PORT=8000`, `DEBUG=False`, `LOG_LEVEL=INFO`, `ALLOWED_METHODS=["GET","POST","PUT","DELETE"]` |
| `DatabaseSettings` | `DATABASE_URL` (PostgresDsn) | No default (required) |
| `CognitoSettings` | `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `COGNITO_REGION` | No defaults (required) |

- All classes use `SettingsConfigDict(env_file=".env")`
- Module-level singletons instantiated at import time — missing required vars raise `ValidationError` before the server starts
- `ALLOWED_ORIGINS` has no default (required) — forces explicit CORS configuration

### 2.4. Database Setup (`app/core/database.py`)

- `create_async_engine()` with `postgresql+asyncpg://` scheme (converted from `DATABASE_URL`'s `postgresql://`)
- Pool config: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True` (handles stale ECS Fargate connections)
- `async_sessionmaker` with `expire_on_commit=False` (prevents lazy-load errors in async context)
- `DeclarativeBase` with explicit naming convention for Alembic constraint auto-generation:
  - `pk`: `%(table_name)s_pkey`
  - `fk`: `%(table_name)s_%(column_0_name)s_fkey`
  - `uq`: `%(table_name)s_%(column_0_name)s_key`
  - `ix`: `%(column_0_label)s_idx`

### 2.5. Dependency Injection (`app/core/dependencies.py`)

- `get_db_session()` — async generator yielding `AsyncSession`, used as the base dependency
- Future repository/service dependencies will chain from `get_db_session` via `Depends()`
- FastAPI's per-request dependency caching ensures a single session flows through the entire chain

### 2.6. Application Entry Point (`app/main.py`)

- App factory function `create_app() -> FastAPI`
- Conditionally set `openapi_url=None` when `APP_ENV` is not `development`
- Mount CORS middleware using `ALLOWED_ORIGINS` and `ALLOWED_METHODS` from settings
- Mount health router directly (no prefix)
- Future routers mounted under `/api/v1` prefix

### 2.7. API Contracts

| Method | Path | Auth | Response | Description |
|---|---|---|---|---|
| `GET` | `/health` | None | `200: {"status": "healthy", "database": "connected"}` or `503: {"status": "unhealthy", "database": "disconnected"}` | Health check with DB connectivity verification |

- Health check executes `SELECT 1` via the async session with a 5-second timeout
- Response schema: `HealthResponse` Pydantic model with `status: str` and `database: str`

---

## 3. Impact and Risk Analysis

- **System Dependencies:** This is the foundational scaffolding — no existing systems are affected. All subsequent specs (database models, auth, user management) depend on this structure being in place.
- **Risk: Database unavailability during health check**
  - *Mitigation:* The health check uses a 5-second timeout on the DB query and returns 503 gracefully rather than hanging or crashing.
- **Risk: Missing environment variables in deployment**
  - *Mitigation:* Pydantic Settings fails fast at startup with a clear `ValidationError` listing all missing fields. The `.env.example` file documents every required variable.
- **Risk: `src/` layout unfamiliarity**
  - *Mitigation:* This is standard Python packaging practice. `pyproject.toml` configures the package source properly.

---

## 4. Testing Strategy

- **Unit tests:** Validate that `Settings` classes raise `ValidationError` for missing required fields and parse valid configs correctly.
- **Integration test:** Start the FastAPI app with `httpx.AsyncClient` and verify `GET /health` returns 200 with expected JSON when a database is available.
- **Test tooling:** pytest + pytest-asyncio + httpx (FastAPI's `TestClient` alternative for async).
- **Test structure:** `tests/unit/` and `tests/integration/` directories, shared fixtures in `tests/conftest.py`.
