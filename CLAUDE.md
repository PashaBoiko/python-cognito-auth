# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python authentication microservice — FastAPI + PostgreSQL + Redis + AWS Cognito. Handles user storage and authentication only; authorization and business logic live in consuming services.

## Spec-driven development (AWOS)

This repo uses **AWOS** (`.awos/` + `context/`) as the spec-development workflow. Always read the relevant spec **before** writing code for a feature, and update its `Status` / acceptance criteria when the work lands.

- **`context/product/`** — durable product context: `product-definition.md`, `architecture.md`, `roadmap.md`. Treat these as the source of truth for *why* the system exists and *what* the high-level stack is.
- **`context/spec/NNN-<slug>/`** — one folder per roadmap feature. Each contains:
  - `functional-spec.md` — the "what" + acceptance criteria checklist (`- [x]` / `- [ ]`).
  - `technical-considerations.md` — the "how": chosen approach, trade-offs, data shapes.
  - `tasks.md` — the engineering breakdown.
- **`.awos/commands/`** — slash-command definitions used to drive the workflow (`/awos:product`, `/awos:roadmap`, `/awos:spec`, `/awos:tech`, `/awos:tasks`, `/awos:implement`, `/awos:verify`, `/awos:hire`, `/awos:architecture`). These are user-invoked; don't run them yourself unless asked.
- **`.awos/templates/`** — the templates those commands fill in. If you create a new spec/architecture doc, copy the matching template rather than freelancing the structure.

Workflow expectations:
- New work starts from a roadmap entry → functional spec → technical considerations → tasks → implementation → `/awos:verify` flips `Status` to `Completed`.
- Existing specs (001 scaffolding, 002 db, 003 auth, 004 redis, 005 user CRUD) are the historical record of why things look the way they do — consult them before refactoring or extending those areas.
- When acceptance criteria change, update the spec file in the same commit as the code; don't let them drift.

## Common commands

All tasks are wired through `taskipy` and must be invoked with `poetry run task <name>`:

| Command | Purpose |
|---|---|
| `poetry run task dev` | Start uvicorn with `--reload` (factory: `app.main:create_app`, dir: `src`) |
| `poetry run task run` | Start uvicorn without reload |
| `poetry run task test` | Run the full pytest suite |
| `poetry run task lint` / `task lint-fix` | Ruff check / auto-fix on `src/` |
| `poetry run task typecheck` | Mypy strict on `src/` |
| `poetry run task check` | lint → typecheck → test (matches CI) |
| `poetry run task migrate` | `PYTHONPATH=src alembic upgrade head` |
| `poetry run task migrate-down` | Rollback one revision |

Run a single test: `poetry run pytest tests/test_users.py::test_name -v`. `pytest` is configured with `asyncio_mode = "auto"` so async tests do **not** need `@pytest.mark.asyncio`.

Local infra (Postgres on **5433**, Redis on **6380** to avoid conflicts with system services):
`docker compose up db redis -d`. Full stack including the app: `docker compose up --build`.

CI (`.github/workflows/ci.yml`) runs ruff check, **`ruff format --check`** (no taskipy alias — run `poetry run ruff format src/` before pushing), mypy, and pytest against ephemeral Postgres + Redis services.

## Architecture

Layered FastAPI app with strict separation between transport, business logic, data access, and ORM:

```
routers → services → repositories → models (SQLAlchemy)
              ↓
        cognito_service / token_service (external IO)
```

- **`src/app/main.py`** — `create_app()` factory. All API routers are mounted under `/api/v1` *except* `health` (mounted at root). `openapi.json` is only exposed when `APP_ENV=development`.
- **`core/config.py`** — Five separate `BaseSettings` classes (`AppSettings`, `DatabaseSettings`, `CognitoSettings`, `JWTSettings`, `RedisSettings`) instantiated as module-level singletons. Missing required env vars raise `ValidationError` at import time, before the ASGI server accepts any request.
- **`core/database.py`** — Single async engine + `async_session_maker`. `expire_on_commit=False` is required to avoid `MissingGreenlet` from implicit lazy-loads under asyncpg. Pydantic's `postgresql://` DSN is rewritten to `postgresql+asyncpg://` here. A `MetaData` naming convention is configured on `Base` so Alembic produces deterministic constraint/index names.
- **`core/redis.py`** — Module-level singleton `redis_client` initialized via the FastAPI `lifespan` context manager (passed into `FastAPI(...)` in `main.py`). `get_redis_client()` raises `RuntimeError` if injected before lifespan startup. Tests that touch token storage need this lifespan to run.
- **`core/dependencies.py`** — All `Depends(...)` providers live here. `get_current_user` does a three-step check: JWT signature → Redis active-session lookup → DB user lookup (with `include_deleted=True` so soft-deleted users get a distinct error). `require_role("admin", ...)` returns a dependency factory that wraps `get_current_user`.

### Auth flow (Cognito Authorization Code)

1. `POST /api/v1/auth` accepts a Cognito authorization `code`.
2. `AuthService.authenticate` → exchange code for Cognito tokens → fetch userinfo → upsert `User` (auto-assigns the `"user"` role from the `roles` table; **the seed role must exist** or `scalar_one()` raises) → store Cognito OAuth tokens on the user row → mint a HS256 JWT (`sub` = user UUID) → register the JWT in Redis via `TokenService.store_token`.
3. The returned application JWT is what every other endpoint expects in `Authorization: Bearer ...`.

### Token storage in Redis

Tokens are **never stored as plaintext**. `TokenService` uses SHA-256 of the JWT as the key (`token:{hash}`). Per-user session tracking lives in a Set at `sessions:{user_id}`. On each new session, `_enforce_session_limit` evicts the oldest entries (sorted by `created_at`) when `REDIS_MAX_SESSIONS` is reached. Redis TTL on each token is set to Cognito's `expires_in` (passed through from `AuthService.authenticate`) so the application JWT and the upstream Cognito access token expire at the same moment.

### Soft delete

Users are never hard-deleted. `User.deleted_at IS NULL` is the active filter. Repository methods accept `include_deleted: bool = False`; `UserService` silently downgrades that flag to `False` for non-admin callers (defense in depth — admin-only endpoints are also gated at the router via `require_role("admin")`). `delete_user` also calls `cognito_service.admin_disable_user(cognito_sub)` to keep Cognito and the DB in sync.

### Schema validation conventions

`UserUpdateRequest` accepts `email` and `role_id` even though regular users can't change them — this is intentional so the **service layer** can return a meaningful 403 ("you are not allowed to update the following fields: ...") rather than silently dropping them. Email changes are *always* forbidden because they would require a separate Cognito flow.

## Database & migrations

- SQLAlchemy 2.0 async with `Mapped[...]` / `mapped_column(...)` style throughout. UUIDs use Postgres-native `gen_random_uuid()` server defaults to avoid an INSERT round-trip.
- Alembic uses the **same engine** as the application (see `alembic/env.py`) — do not introduce a second engine. The env file inserts `src/` onto `sys.path` so it works without `PYTHONPATH=src`, but the taskipy alias still sets it for consistency.
- Migration filenames are date-prefixed: `%(year)d-%(month).2d-%(day).2d_%(slug)s.py` (configured in `alembic.ini`).
- `Role.name == "user"` and `Role.name == "admin"` are referenced by code; ensure the `roles` table is seeded after a fresh migrate.

## Conventions worth respecting

- **Strict mypy is on** (`tool.mypy: strict = true`). New code needs full type hints. The only `disable_error_code` overrides are for `app.core.config` (`call-arg`, due to pydantic-settings init signature) and `app.models.*` (`misc`, due to SQLAlchemy descriptors).
- Ruff selects `E, F, I, UP, B, SIM`; `B008` is ignored (FastAPI's `Depends()` in defaults).
- Routers stay thin: parse + delegate to a service + return a Pydantic schema (`Response.model_validate(orm_obj)`). Business rules and authorization decisions live in services.
- Do not log secrets, JWTs, or OAuth tokens. The token hash is fine; the token is not.
