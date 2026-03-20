.PHONY: install dev run test lint typecheck check db db-stop migrate migrate-down migrate-create up down clean help

# ── Setup ──────────────────────────────────────────────
install:  ## Install all dependencies
	poetry install

# ── Development ────────────────────────────────────────
dev:  ## Start app with hot-reload
	poetry run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --app-dir src --reload

run:  ## Start app without reload (production-like)
	poetry run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --app-dir src

# ── Quality ────────────────────────────────────────────
test:  ## Run tests
	poetry run pytest

lint:  ## Run linter (ruff)
	poetry run ruff check src/

lint-fix:  ## Run linter and auto-fix issues
	poetry run ruff check src/ --fix

typecheck:  ## Run type checker (mypy)
	poetry run mypy src/

check: lint typecheck test  ## Run all checks (lint + typecheck + test)

# ── Database ───────────────────────────────────────────
db:  ## Start PostgreSQL in Docker
	docker compose up db -d

db-stop:  ## Stop PostgreSQL
	docker compose stop db

# ── Migrations ─────────────────────────────────────────
migrate:  ## Run all pending migrations
	PYTHONPATH=src poetry run alembic upgrade head

migrate-down:  ## Rollback last migration
	PYTHONPATH=src poetry run alembic downgrade -1

migrate-create:  ## Create new migration (usage: make migrate-create msg="description")
	PYTHONPATH=src poetry run alembic revision --autogenerate -m "$(msg)"

# ── Docker (full stack) ────────────────────────────────
up:  ## Start everything (DB + app) in Docker
	docker compose up --build -d

down:  ## Stop everything
	docker compose down

clean:  ## Stop everything and remove volumes (deletes DB data!)
	docker compose down -v

# ── Help ───────────────────────────────────────────────
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'
