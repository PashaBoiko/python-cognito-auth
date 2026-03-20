# Functional Specification: Auth — Token Exchange & Verification

- **Roadmap Item:** User Registration + User Login & Token Verification (combined — token exchange pattern replaces separate signup/login)
- **Status:** Completed
- **Author:** Poe

---

## 1. Overview and Rationale (The "Why")

The auth microservice uses a **delegated OAuth authentication pattern** (same as lexiclab-nest-api). The frontend handles the Cognito OAuth flow (Google login). The backend's role is to:

1. Exchange the OAuth authorization code for Cognito tokens
2. Extract user identity (email, Cognito sub)
3. Find or create the user in PostgreSQL
4. Issue a backend JWT for subsequent API calls

There is **no direct signup or login endpoint**. User creation happens automatically on first token exchange. This is simpler, more secure (no password management), and follows the proven lexiclab pattern.

**Success looks like:** A user can authenticate via Google OAuth through Cognito, the backend exchanges the code, creates/finds the user, and returns a backend JWT that protects all subsequent API calls.

---

## 2. Functional Requirements (The "What")

### 2.1. Token Exchange Endpoint

- `POST /auth` accepts an OAuth authorization code from the frontend and returns a backend JWT + user data.
- **Request:** `{"code": "authorization_code_from_cognito"}`
- **Flow:**
  1. Exchange the code for Cognito tokens (access_token, refresh_token, id_token) via Cognito's `/oauth2/token` endpoint
  2. Call Cognito's `/oauth2/userInfo` to get the user's email and sub
  3. Look up the user by email in PostgreSQL
  4. If the user exists: update their stored OAuth tokens
  5. If the user is new: create a user record with the default `user` role
  6. Generate a backend JWT and store it on the user record
  7. Return the user object + JWT
- **Response (200):**
  ```json
  {
    "user": {"id": "uuid", "email": "...", "cognito_sub": "...", "role": "user"},
    "token": "backend_jwt_token",
    "expires_in": 3600
  }
  ```
- **Acceptance Criteria:**
  - [x] `POST /auth` accepts `{"code": "..."}` and returns user + token
  - [x] The endpoint exchanges the code with Cognito's OAuth token endpoint
  - [x] The endpoint retrieves user info from Cognito's userInfo endpoint
  - [x] A new user is created in PostgreSQL with the default `user` role on first login
  - [x] An existing user's OAuth tokens are updated on subsequent logins
  - [x] A backend JWT is generated, stored on the user record, and returned
  - [x] Invalid or expired authorization codes return a clear error (401)

### 2.2. Token Validation Endpoint

- `POST /auth/validate` verifies the current backend JWT and returns the user if valid.
- **Acceptance Criteria:**
  - [x] `POST /auth/validate` with a valid Bearer token returns the user object
  - [x] An invalid or expired token returns 401

### 2.3. Logout Endpoint

- `POST /auth/logout` clears the user's stored JWT, invalidating the session.
- **Acceptance Criteria:**
  - [x] `POST /auth/logout` clears the JWT from the user record in the database
  - [x] The cleared token can no longer be used for authentication

### 2.4. Auth Guard (JWT Middleware)

- A reusable guard/middleware that protects routes by verifying the backend JWT.
- **Flow:** Extract Bearer token → verify JWT signature → look up user in DB with matching token → attach user to request
- **Acceptance Criteria:**
  - [x] Protected routes reject requests without a valid Bearer token (401)
  - [x] The guard verifies JWT signature using a secret from environment config
  - [x] The guard checks that the token matches the one stored in the database (enables invalidation)
  - [x] The authenticated user is available to route handlers via dependency injection

### 2.5. Database Changes

- The `users` table needs additional columns to support JWT and OAuth token storage.
- **New columns:**
  - `token` — string, nullable (stores the current backend JWT)
  - `oauth_access_token` — string, nullable
  - `oauth_refresh_token` — string, nullable
  - `oauth_id_token` — string, nullable
  - `oauth_expires_at` — timestamp, nullable
- **New environment variable:**
  - `JWT_SECRET` — secret key for signing backend JWTs
- **Acceptance Criteria:**
  - [x] An Alembic migration adds the new columns to the `users` table
  - [x] `JWT_SECRET` is added to Pydantic Settings and `.env.example`

---

## 3. Scope and Boundaries

### In-Scope

- `POST /auth` — OAuth code → token exchange → find/create user → return backend JWT
- `POST /auth/validate` — verify current JWT, return user
- `POST /auth/logout` — invalidate JWT
- Auth guard middleware for protecting routes
- Cognito OAuth integration (token exchange + userInfo)
- Backend JWT generation and storage
- Database migration for new user columns
- User repository (create, find by email, update tokens)

### Out-of-Scope

- Frontend OAuth flow (handled by the frontend app)
- Cognito Hosted UI configuration (AWS console setup)
- Token refresh endpoint (can be added later)
- Direct email+password signup/login (not using this pattern)
- User Lookup endpoints (Phase 3)
- Role Management endpoints (Phase 3)
- OAuth with providers other than Google (future)
