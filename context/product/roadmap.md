# Product Roadmap: Python Auth Microservice

_This roadmap outlines our strategic direction based on customer needs and business goals. It focuses on the "what" and "why," not the technical "how."_

---

### Phase 1: Foundation — Project Setup & Data Layer

_The highest priority features that form the core infrastructure and data model._

- [x] **Project Scaffolding**
  - [x] **Clean Architecture Setup:** Establish the project structure with layer separation (routers, services, repositories, models) and dependency injection.
  - [x] **Environment Configuration:** Set up Pydantic Settings for managing database URLs, Cognito credentials, and other environment variables.

- [x] **Database & Persistence**
  - [x] **Roles Table:** Create the `roles` table (UUID, name, description, timestamps) with SQLAlchemy 2.0 models and async support.
  - [x] **Users Table:** Create the `users` table (UUID, email, cognito_sub, role_id FK, timestamps) with the one-to-many relationship to roles.
  - [x] **Alembic Migrations:** Initialize Alembic and create the initial migration for both tables.

---

### Phase 2: Core Auth — Registration, Login & Token Verification

_Once the data layer is in place, we build the authentication flows powered by AWS Cognito._

- [x] **User Registration** _(implemented as OAuth token exchange — auto-creates user on first login)_
  - [x] **Cognito Signup Integration:** Register new users in AWS Cognito and store the resulting `cognito_sub`, email, and default role in PostgreSQL via `POST /api/v1/auth`.
  - [x] **Cognito-to-Internal User Mapping:** Ensure every Cognito user is reliably mapped to an internal user record.

- [x] **User Login & Token Verification** _(implemented as OAuth token exchange + backend JWT)_
  - [x] **Login via Cognito:** Authenticate users through Cognito and return backend JWT via `POST /api/v1/auth`.
  - [x] **Token Verification Endpoint:** Validate backend JWTs via `POST /api/v1/auth/validate`.
  - [x] **Token Verification Middleware:** Auth guard dependency verifies backend JWT + DB match on protected routes.

---

### Phase 3: User & Role Management — API Completeness

_With auth working, expose the user and role management endpoints for consuming services._

- [ ] **User Lookup**
  - [ ] **Get User by ID:** Retrieve a user's details by their internal UUID via `GET /users/{id}`.
  - [ ] **Get User by Email:** Retrieve a user's details by email address via `GET /users/by-email/{email}`.

- [ ] **Role Management**
  - [ ] **List Roles:** Return all available roles via `GET /roles`.
  - [ ] **Create Role:** Allow creation of new roles via `POST /roles`.
  - [ ] **Role Assignment:** Attach/update a user's role via the user-role relationship.
