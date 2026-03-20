# Technical Specification: Database & Persistence

- **Functional Specification:** `context/spec/002-database-persistence/functional-spec.md`
- **Status:** Completed
- **Author(s):** Poe

---

## 1. High-Level Technical Approach

Create SQLAlchemy 2.0 async models for `roles` and `users` tables, inheriting from the existing `Base` in `database.py`. Initialize Alembic with async template, configure it to use the project's engine and metadata, auto-generate the initial migration, and seed default roles (`user`, `admin`) within the migration using `op.bulk_insert`.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1. New Files

| File | Responsibility |
|---|---|
| `src/app/models/role.py` | `Role` SQLAlchemy model |
| `src/app/models/user.py` | `User` SQLAlchemy model |
| `src/app/models/__init__.py` | Re-export both models (registers them on `Base.metadata`) |
| `alembic.ini` | Alembic configuration (project root) |
| `alembic/env.py` | Async migration runner wired to existing engine |
| `alembic/versions/` | Migration files directory |

### 2.2. Data Models

**`roles` table:**

| Column | Type | Constraints | Default |
|---|---|---|---|
| `id` | `UUID` | PK | `gen_random_uuid()` (server-side) |
| `name` | `String(50)` | UNIQUE, NOT NULL | — |
| `description` | `String(255)` | nullable | `NULL` |
| `created_at` | `DateTime(timezone=True)` | NOT NULL | `now()` (server-side) |

**`users` table:**

| Column | Type | Constraints | Default |
|---|---|---|---|
| `id` | `UUID` | PK | `gen_random_uuid()` (server-side) |
| `email` | `String(255)` | UNIQUE, NOT NULL | — |
| `cognito_sub` | `String(255)` | UNIQUE, NOT NULL | — |
| `role_id` | `UUID` | FK → `roles.id`, NOT NULL | — |
| `created_at` | `DateTime(timezone=True)` | NOT NULL | `now()` (server-side) |
| `updated_at` | `DateTime(timezone=True)` | NOT NULL | `now()` (server-side), `onupdate=func.now()` |

**Relationships:**
- `Role.users` — one-to-many (`relationship("User", back_populates="role")`)
- `User.role` — many-to-one (`relationship("Role", back_populates="users", lazy="selectin")`)

Use `lazy="selectin"` on `User.role` to avoid async lazy-load errors when accessing the role after a query.

### 2.3. Model Implementation Pattern

- Use SQLAlchemy 2.0 `Mapped[]` + `mapped_column()` syntax (compatible with mypy strict)
- UUID columns use `server_default=text("gen_random_uuid()")` — PostgreSQL 13+ native, no extension needed
- Timestamps use `server_default=func.now()` for `created_at`; `updated_at` adds `onupdate=func.now()`
- Import `Base` from `app.core.database`

### 2.4. Alembic Setup

- Initialize with async template: `alembic init -t async alembic`
- `alembic.ini`: set `sqlalchemy.url` to a placeholder (overridden by `env.py`)
- `alembic/env.py`: import `Base.metadata` and the existing `engine` from `app.core.database`; import `app.models` to register all models
- Migration file template: use `%%(year)d-%%(month).2d-%%(day).2d_%%(slug)s` for readable filenames

### 2.5. Initial Migration

- Auto-generate with: `alembic revision --autogenerate -m "create roles and users tables"`
- The migration `upgrade()` creates `roles` table first (referenced by FK), then `users`
- Seed data via `op.bulk_insert` on the roles table within the same migration:
  - `{"name": "user", "description": "Default role for new users"}`
  - `{"name": "admin", "description": "Administrator role"}`
- The `downgrade()` drops `users` first (FK dependency), then `roles`

### 2.6. Makefile Commands

Add to the existing Makefile:

| Command | What it does |
|---|---|
| `make migrate` | Run `alembic upgrade head` |
| `make migrate-down` | Run `alembic downgrade -1` |
| `make migrate-create` | Run `alembic revision --autogenerate -m "..."` |

---

## 3. Impact and Risk Analysis

- **System Dependencies:** The existing `Base` and `engine` from `database.py` are reused — no changes to existing code.
- **Risk: Model import order** — `alembic/env.py` must import `app.models` to register models on `Base.metadata`. If this import is missing, autogenerate produces empty migrations.
  - *Mitigation:* Explicit `import app.models` with a `noqa` comment in `env.py`.
- **Risk: FK ordering in migration** — `users.role_id` references `roles.id`, so `roles` must be created first.
  - *Mitigation:* Alembic autogenerate handles this correctly. Verify in review.
- **Risk: Seed data idempotency** — Running the migration twice would fail on duplicate role names.
  - *Mitigation:* Alembic tracks applied migrations. A migration only runs once.

---

## 4. Testing Strategy

- **Migration test:** Run `alembic upgrade head` against a clean database, verify both tables exist with correct columns and constraints. Run `alembic downgrade base`, verify tables are dropped.
- **Seed data test:** After `upgrade head`, query the `roles` table and confirm `user` and `admin` roles exist with correct descriptions.
- **Model test:** Create a `Role` and `User` instance via the async session, verify the relationship works (user.role returns the role object).
