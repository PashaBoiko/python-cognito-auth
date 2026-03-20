# Functional Specification: Database & Persistence

- **Roadmap Item:** Database & Persistence — Create the roles and users tables with SQLAlchemy 2.0 models, relationships, and Alembic migrations.
- **Status:** Completed
- **Author:** Poe

---

## 1. Overview and Rationale (The "Why")

The auth microservice needs a data layer before any feature can store or retrieve information. Without the `roles` and `users` tables, subsequent work (registration, login, user lookup, role management) has no persistence layer to work with.

This specification defines the two core database tables, their relationship, the Alembic migration setup, and seed data for default roles. After this work is complete, the database schema is ready for all Phase 2 and Phase 3 features.

**Success looks like:** Running `alembic upgrade head` creates both tables with correct columns, constraints, and relationships, and seeds the default `user` and `admin` roles.

---

## 2. Functional Requirements (The "What")

### 2.1. Roles Table

- The system must store roles with the following structure:
  - `id` — UUID, primary key, auto-generated
  - `name` — string, unique, not null
  - `description` — string, nullable
  - `created_at` — timestamp, auto-set on creation
- **Acceptance Criteria:**
  - [x] A `roles` SQLAlchemy model exists with all specified columns
  - [x] The `name` column has a unique constraint
  - [x] The `id` column is a UUID with a server-side default
  - [x] The `created_at` column is auto-populated with the current timestamp

### 2.2. Users Table

- The system must store users with the following structure:
  - `id` — UUID, primary key, auto-generated
  - `email` — string, unique, not null
  - `cognito_sub` — string, unique, not null (Cognito user identifier)
  - `role_id` — UUID, foreign key referencing `roles.id`, not null
  - `created_at` — timestamp, auto-set on creation
  - `updated_at` — timestamp, auto-updated on modification
- **Acceptance Criteria:**
  - [x] A `users` SQLAlchemy model exists with all specified columns
  - [x] The `email` column has a unique constraint
  - [x] The `cognito_sub` column has a unique constraint
  - [x] The `role_id` column is a foreign key to `roles.id` and is not nullable
  - [x] The `created_at` column is auto-populated on creation
  - [x] The `updated_at` column is auto-updated on every modification

### 2.3. Relationships

- One role can have many users. A user belongs to exactly one role.
- **Acceptance Criteria:**
  - [x] The `Role` model has a `users` relationship (one-to-many)
  - [x] The `User` model has a `role` relationship (many-to-one)

### 2.4. Alembic Migrations

- Alembic must be initialized and configured to work with the async SQLAlchemy engine and the project's `Base` metadata.
- A migration must create both tables.
- **Acceptance Criteria:**
  - [x] Alembic is initialized with `alembic.ini` and a migrations directory
  - [x] Alembic `env.py` is configured to use the project's `Base.metadata` and async engine
  - [x] Running `alembic upgrade head` creates both `roles` and `users` tables
  - [x] Running `alembic downgrade base` drops both tables cleanly

### 2.5. Seed Data

- After the migration runs, default roles must exist in the database.
- **Acceptance Criteria:**
  - [x] A `user` role is created with description "Default role for new users"
  - [x] An `admin` role is created with description "Administrator role"
  - [x] Seed data is applied as part of the migration (data migration), not a separate script

---

## 3. Scope and Boundaries

### In-Scope

- SQLAlchemy 2.0 async models for `roles` and `users` tables
- One-to-many relationship between roles and users
- Alembic initialization and configuration for async
- Initial migration creating both tables
- Seed data for `user` and `admin` roles within the migration
- Alembic `Makefile` commands for running migrations

### Out-of-Scope

- User Registration / Cognito Signup Integration (Phase 2)
- User Login & Token Verification (Phase 2)
- User Lookup endpoints (Phase 3)
- Role Management endpoints (Phase 3)
- Repository layer implementation (will be created alongside each endpoint's spec)
- Database indexes beyond unique constraints (optimize later based on query patterns)
