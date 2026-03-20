# Technical Specification: Auth — Token Exchange & Verification

- **Functional Specification:** `context/spec/003-auth-token-exchange/functional-spec.md`
- **Status:** Completed
- **Author(s):** Poe

---

## 1. High-Level Technical Approach

Implement the Cognito OAuth token exchange pattern (same as lexiclab-nest-api, ported to Python/FastAPI). The backend exchanges an OAuth authorization code for Cognito tokens via HTTP calls to Cognito's `/oauth2/token` and `/oauth2/userInfo` endpoints, finds or creates the user in PostgreSQL, generates a backend JWT (signed with `JWT_SECRET`), stores it on the user record, and returns it. An auth guard dependency verifies the backend JWT + DB match on protected routes.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1. New & Modified Files

| File | Action | Responsibility |
|---|---|---|
| `src/app/services/cognito_service.py` | Create | Cognito HTTP calls (token exchange, userInfo) |
| `src/app/services/auth_service.py` | Create | Auth business logic (find/create user, generate JWT) |
| `src/app/repositories/user_repository.py` | Create | User DB operations (find by email, create, update tokens) |
| `src/app/routers/auth.py` | Create | Auth endpoints (POST /auth, POST /auth/validate, POST /auth/logout) |
| `src/app/schemas/auth.py` | Create | Request/response Pydantic models |
| `src/app/core/dependencies.py` | Modify | Add auth guard dependency (`get_current_user`) |
| `src/app/core/config.py` | Modify | Add `JWT_SECRET`, `COGNITO_URL`, `COGNITO_CLIENT_SECRET`, `COGNITO_LOGIN_REDIRECT_URL` |
| `src/app/models/user.py` | Modify | Add token + OAuth columns |
| `src/app/main.py` | Modify | Mount auth router under `/api/v1` |
| `pyproject.toml` | Modify | Move `httpx` to prod dependencies |
| `alembic/versions/` | Create | Migration for new user columns |

### 2.2. Database Changes (User Model)

New columns on `users` table:

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `token` | `Text` | nullable | Current backend JWT |
| `oauth_access_token` | `Text` | nullable | Cognito access token |
| `oauth_refresh_token` | `Text` | nullable | Cognito refresh token |
| `oauth_id_token` | `Text` | nullable | Cognito ID token |
| `oauth_expires_at` | `DateTime(timezone=True)` | nullable | Cognito token expiration |

Migration: `make migrate-create msg="add token and oauth columns to users"`

### 2.3. Environment Configuration Changes

Add to `CognitoSettings`:

| Variable | Type | Required | Example |
|---|---|---|---|
| `COGNITO_URL` | `str` | Yes | `https://your-domain.auth.us-east-1.amazoncognito.com` |
| `COGNITO_CLIENT_SECRET` | `str` | Yes | Cognito app client secret |
| `COGNITO_LOGIN_REDIRECT_URL` | `str` | Yes | `http://localhost:3000/auth/callback` |

Add new `JWTSettings` class:

| Variable | Type | Required | Example |
|---|---|---|---|
| `JWT_SECRET` | `str` | Yes | Random secret string for signing backend JWTs |
| `JWT_EXPIRATION_HOURS` | `int` | No (default: 24) | Token lifetime in hours |

### 2.4. Cognito Service (`services/cognito_service.py`)

Two async methods using `httpx.AsyncClient`:

**`exchange_code_for_token(code: str)`**
- `POST {COGNITO_URL}/oauth2/token`
- Content-Type: `application/x-www-form-urlencoded`
- Body: `grant_type=authorization_code`, `client_id`, `client_secret`, `code`, `redirect_uri`
- Returns: `access_token`, `refresh_token`, `id_token`, `expires_in`

**`get_user_info(access_token: str)`**
- `GET {COGNITO_URL}/oauth2/userInfo`
- Header: `Authorization: Bearer {access_token}`
- Returns: `sub`, `email`

Use `httpx.AsyncClient` (not `requests`) since FastAPI is async. Wrap Cognito HTTP errors with clear error messages. Set 5-second timeout.

### 2.5. User Repository (`repositories/user_repository.py`)

| Method | Description |
|---|---|
| `get_by_email(email: str)` | Find user by email, return `User` or `None` |
| `create(email, cognito_sub, role_id)` | Create new user with default role |
| `update_oauth_tokens(user_id, tokens)` | Update OAuth token columns |
| `update_token(user_id, token)` | Update backend JWT column |
| `get_by_id_and_token(user_id, token)` | Find user matching both ID and token (for guard) |
| `clear_token(user_id)` | Set token to `None` (logout) |

All methods use the injected `AsyncSession`.

### 2.6. Auth Service (`services/auth_service.py`)

**`authenticate(code: str)`** — orchestrates the full flow:
1. Call `cognito_service.exchange_code_for_token(code)`
2. Call `cognito_service.get_user_info(access_token)`
3. Call `user_repository.get_by_email(email)`
4. If exists: `user_repository.update_oauth_tokens(user, tokens)`
5. If new: look up default `user` role, then `user_repository.create(email, sub, role_id)`
6. Generate backend JWT using `python-jose`: `jwt.encode({"sub": str(user.id), "email": user.email}, JWT_SECRET, algorithm="HS256")`
7. Call `user_repository.update_token(user.id, token)`
8. Return user + token + expires_in

### 2.7. Auth Guard (`core/dependencies.py`)

**`get_current_user()`** — FastAPI dependency:
1. Extract `Authorization: Bearer <token>` from request headers
2. Decode JWT with `python-jose`: `jwt.decode(token, JWT_SECRET, algorithms=["HS256"])`
3. Extract `user_id` from payload `sub`
4. Call `user_repository.get_by_id_and_token(user_id, token)` — verifies token is still active in DB
5. If user not found or token mismatch: raise `HTTPException(401)`
6. Return the `User` object

This dependency can be injected into any route: `current_user: User = Depends(get_current_user)`

### 2.8. API Contracts

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| `POST` | `/api/v1/auth` | No | `{"code": "..."}` | `{"user": {...}, "token": "...", "expires_in": 3600}` |
| `POST` | `/api/v1/auth/validate` | Bearer | — | `{"user": {...}}` |
| `POST` | `/api/v1/auth/logout` | Bearer | — | `{"message": "Logged out"}` |

### 2.9. Dependency Changes

Move `httpx` from dev to prod dependencies in `pyproject.toml`.

---

## 3. Impact and Risk Analysis

- **Cognito availability:** Token exchange depends on Cognito being reachable. If Cognito is down, login fails.
  - *Mitigation:* Clear error messages and timeouts on Cognito HTTP calls (5-second timeout).
- **JWT_SECRET rotation:** Changing the secret invalidates all existing tokens.
  - *Mitigation:* Acceptable for MVP. Token refresh endpoint can be added later.
- **OAuth token storage:** Storing tokens in plaintext in the DB is a risk if the DB is compromised.
  - *Mitigation:* Acceptable for MVP. Encryption at rest can be added later.
- **httpx as prod dependency:** Currently dev-only. Must be moved to prod.
  - *Mitigation:* Simple `pyproject.toml` change.

---

## 4. Testing Strategy

- **Unit tests:** Mock Cognito HTTP responses with `httpx`'s mock transport. Test auth service logic (new user creation, existing user update, JWT generation).
- **Integration tests:** Test the full `POST /auth` flow with mocked Cognito responses. Test auth guard rejects invalid tokens.
- **Manual test:** Requires a configured Cognito user pool with Google OAuth. Exchange a real authorization code to verify end-to-end.
