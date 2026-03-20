# Tasks: Database & Persistence

**Spec:** `context/spec/002-database-persistence/`
**Prerequisites:** PostgreSQL must be running via `make db`.

---

## Slice 1: SQLAlchemy Models (Role + User)

_After this slice: models exist, app still starts, no DB schema changes yet._

- [x] **Slice 1: SQLAlchemy Models (Role + User)**
  - [x] Create `src/app/models/role.py`: define `Role` model inheriting `Base` with columns `id` (UUID, PK, server_default gen_random_uuid), `name` (String(50), unique, not null), `description` (String(255), nullable), `created_at` (DateTime with timezone, server_default now). Add `users` relationship (one-to-many). **[Agent: postgres-database]**
  - [x] Create `src/app/models/user.py`: define `User` model inheriting `Base` with columns `id` (UUID, PK, server_default gen_random_uuid), `email` (String(255), unique, not null), `cognito_sub` (String(255), unique, not null), `role_id` (UUID, FK to roles.id, not null), `created_at` (DateTime, server_default now), `updated_at` (DateTime, server_default now, onupdate now). Add `role` relationship (many-to-one, lazy="selectin"). **[Agent: postgres-database]**
  - [x] Update `src/app/models/__init__.py`: import and re-export `Role` and `User` so they register on `Base.metadata`. **[Agent: postgres-database]**
  - [x] **Verify:** Start the app with `make dev` — confirm it boots without errors. Run `PYTHONPATH=src poetry run python -c "from app.models import Role, User; print('Models OK')"` to confirm imports work. **[Agent: postgres-database]**

---

## Slice 2: Alembic Setup & Initial Migration

_After this slice: `make migrate` creates both tables and seeds default roles in PostgreSQL._

- [x] **Slice 2: Alembic Setup & Initial Migration**
  - [x] Initialize Alembic with async template: run `alembic init -t async alembic` at project root. Configure `alembic.ini` with placeholder URL and readable file template. **[Agent: postgres-database]**
  - [x] Configure `alembic/env.py`: wire it to use `Base.metadata` and the existing async `engine` from `app.core.database`. Add `import app.models` to register all models. **[Agent: postgres-database]**
  - [x] Generate the initial migration: `alembic revision --autogenerate -m "create roles and users tables"`. After generation, manually add `op.bulk_insert` seed data for `user` and `admin` roles in the `upgrade()` function. **[Agent: postgres-database]**
  - [x] Add Makefile commands: `make migrate` (alembic upgrade head), `make migrate-down` (alembic downgrade -1), `make migrate-create` (alembic revision --autogenerate). **[Agent: python-backend]**
  - [x] **Verify:** Run `make migrate` against the running PostgreSQL. Connect to the database and confirm: (1) `roles` table exists with correct columns and constraints, (2) `users` table exists with FK to roles, (3) `user` and `admin` roles are seeded. Then run `make migrate-down` and confirm both tables are dropped. Run `make migrate` again to leave the DB in a clean state. **[Agent: postgres-database]**
