# Python Auth Microservice

A production-ready authentication microservice built with FastAPI, PostgreSQL, Redis, and AWS Cognito. Handles user storage and authentication only — authorization and business logic are delegated to consuming services.

## Tech Stack

- **Python 3.11+** / **FastAPI** / **Pydantic v2**
- **PostgreSQL 16** / **SQLAlchemy 2.0** (async) / **Alembic**
- **Redis** (multi-session token storage)
- **AWS Cognito** (registration, login, OAuth 2.0 token exchange)
- **Docker** / **Docker Compose**

## Project Structure

```
src/app/
├── main.py              # FastAPI app factory
├── core/
│   ├── config.py        # Pydantic Settings (env configuration)
│   ├── database.py      # SQLAlchemy async engine & session
│   ├── dependencies.py  # FastAPI Depends() providers
│   └── redis.py         # Redis connection setup
├── routers/             # API endpoint definitions
│   ├── auth.py          # /auth (login, signup, callback)
│   ├── health.py        # /health
│   └── users.py         # /users (CRUD)
├── schemas/             # Pydantic request/response models
│   ├── auth.py          # Auth request/response shapes
│   ├── health.py        # HealthResponse
│   └── user.py          # User CRUD request/response shapes
├── services/            # Business logic layer
│   ├── auth_service.py  # Authentication logic
│   ├── cognito_service.py # AWS Cognito integration
│   ├── token_service.py # Redis token management
│   └── user_service.py  # User CRUD logic
├── repositories/        # Data access layer
│   └── user_repository.py # User database queries
└── models/              # SQLAlchemy ORM models
    ├── user.py          # User table
    └── role.py          # Role table
```

## Prerequisites

- **Python 3.11+**
- **Poetry** (dependency management)
- **Docker** and **Docker Compose** (for PostgreSQL and Redis)

## Getting Started

### 1. Clone and install dependencies

```bash
git clone <repository-url>
cd python-auth
poetry install
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | *(required)* |
| `COGNITO_USER_POOL_ID` | AWS Cognito user pool ID | *(required)* |
| `COGNITO_CLIENT_ID` | AWS Cognito app client ID | *(required)* |
| `COGNITO_REGION` | AWS region for Cognito | *(required)* |
| `COGNITO_URL` | Cognito hosted UI base URL | *(required)* |
| `COGNITO_LOGIN_REDIRECT_URL` | OAuth redirect URI | *(required)* |
| `JWT_SECRET` | Secret key for signing JWTs | *(required)* |
| `REDIS_URL` | Redis connection URL | *(required)* |
| `ALLOWED_ORIGINS` | CORS allowed origins (JSON list) | *(required)* |
| `APP_ENV` | Environment (`development`/`staging`/`production`) | `production` |
| `APP_HOST` | Bind host | `0.0.0.0` |
| `APP_PORT` | Bind port | `8000` |
| `DEBUG` | Debug mode | `false` |
| `LOG_LEVEL` | Log level | `INFO` |
| `COGNITO_CLIENT_SECRET` | Cognito app client secret | `None` |
| `COGNITO_SCOPE` | OAuth 2.0 scopes | `openid email profile` |
| `REDIS_MAX_SESSIONS` | Max concurrent sessions per user | `3` |
| `ALLOWED_METHODS` | CORS allowed methods (JSON list) | `["GET","POST","PUT","DELETE"]` |

### 3. Start PostgreSQL and Redis

```bash
docker compose up db redis -d
```

This starts PostgreSQL 16 on **port 5433** and Redis on **port 6380** (mapped to avoid conflicts with local instances).

### 4. Run database migrations

```bash
poetry run task migrate
```

### 5. Start the application

```bash
poetry run task dev
```

The API is now available at `http://localhost:8000`.

### 6. Verify it works

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy", "database": "connected"}
```

## Running with Docker Compose (full stack)

To run PostgreSQL, Redis, and the application together:

```bash
docker compose up --build
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Root liveness probe |
| `GET` | `/health` | Health check with DB connectivity verification |
| `POST` | `/auth/signup` | Register a new user |
| `POST` | `/auth/login` | Authenticate a user |
| `GET` | `/auth/callback` | OAuth 2.0 callback |
| `GET` | `/users` | List users |
| `GET` | `/users/{id}` | Get user by ID |
| `PUT` | `/users/{id}` | Update user |
| `DELETE` | `/users/{id}` | Soft-delete user |
| `GET` | `/docs` | OpenAPI docs (development only) |

## Development

### Available tasks

All tasks run via [taskipy](https://github.com/taskipy/taskipy):

```bash
poetry run task dev          # Start app with hot-reload
poetry run task run          # Start app (production-like)
poetry run task test         # Run tests
poetry run task lint         # Check code style (ruff)
poetry run task lint-fix     # Auto-fix style issues
poetry run task typecheck    # Check type hints (mypy)
poetry run task check        # Run all checks: lint + typecheck + test
poetry run task migrate      # Apply pending database migrations
poetry run task migrate-down # Rollback last migration
```

## API Documentation

OpenAPI docs are available at `/docs` when `APP_ENV=development`. They are automatically hidden in `staging` and `production` environments.
