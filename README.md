# Python Auth Microservice

A production-ready authentication microservice built with FastAPI, PostgreSQL, and AWS Cognito. Handles user storage and authentication only — authorization and business logic are delegated to consuming services.

## Tech Stack

- **Python 3.11+** / **FastAPI** / **Pydantic v2**
- **PostgreSQL 16** / **SQLAlchemy 2.0** (async) / **Alembic**
- **AWS Cognito** (registration, login, JWT tokens)
- **Docker** / **Docker Compose**

## Project Structure

```
src/app/
├── main.py              # FastAPI app factory
├── core/
│   ├── config.py        # Pydantic Settings (env configuration)
│   ├── database.py      # SQLAlchemy async engine & session
│   └── dependencies.py  # FastAPI Depends() providers
├── routers/             # API endpoint definitions
│   └── health.py        # GET /health
├── schemas/             # Pydantic request/response models
│   └── health.py        # HealthResponse
├── services/            # Business logic layer
├── repositories/        # Data access layer
└── models/              # SQLAlchemy ORM models
```

## Prerequisites

- **Python 3.11+**
- **Poetry** (dependency management)
- **Docker** and **Docker Compose** (for PostgreSQL)

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

Edit `.env` with your values. Required variables:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | *(required)* |
| `COGNITO_USER_POOL_ID` | AWS Cognito user pool ID | *(required)* |
| `COGNITO_CLIENT_ID` | AWS Cognito app client ID | *(required)* |
| `COGNITO_REGION` | AWS region for Cognito | *(required)* |
| `ALLOWED_ORIGINS` | CORS allowed origins (JSON list) | *(required)* |
| `APP_ENV` | Environment (`development`/`staging`/`production`) | `production` |
| `APP_HOST` | Bind host | `0.0.0.0` |
| `APP_PORT` | Bind port | `8000` |
| `DEBUG` | Debug mode | `false` |
| `LOG_LEVEL` | Log level | `INFO` |
| `ALLOWED_METHODS` | CORS allowed methods (JSON list) | `["GET","POST","PUT","DELETE"]` |

### 3. Start PostgreSQL

```bash
make db
```

This starts PostgreSQL 16 on **port 5433** (mapped to avoid conflicts with other local instances).

### 4. Run the application

```bash
make dev
```

The API is now available at `http://localhost:8000`.

### 5. Verify it works

```bash
# Root endpoint
curl http://localhost:8000/

# Health check (includes DB connectivity)
curl http://localhost:8000/health
```

Expected health check response:
```json
{"status": "healthy", "database": "connected"}
```

## Running with Docker Compose (full stack)

To run both PostgreSQL and the application in Docker:

```bash
docker compose up --build
```

This will:
- Start PostgreSQL 16 on port 5433
- Build and start the FastAPI app on port 8000
- Mount `./src` for live code reloading during development

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Root liveness probe |
| `GET` | `/health` | Health check with DB connectivity verification |
| `GET` | `/docs` | OpenAPI docs (development only) |

## Development

### Run tests

```bash
make test
```

### Lint and type check

```bash
make lint
make typecheck
```

## API Documentation

OpenAPI docs are available at `/docs` when `APP_ENV=development`. They are automatically hidden in `staging` and `production` environments.
