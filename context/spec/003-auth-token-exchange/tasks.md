# Tasks: Auth — Token Exchange & Verification

**Spec:** `context/spec/003-auth-token-exchange/`
**Prerequisites:** PostgreSQL running via `make db`. For full end-to-end testing of `POST /auth`, a configured Cognito user pool with Google OAuth is needed (manual test only).

---

## Slice 1: Config, DB Migration & Dependencies

_After this slice: new env vars and DB columns are in place, httpx is a prod dependency. App still starts._

- [x] **Slice 1: Config, DB Migration & Dependencies**
  - [x] Move `httpx` from dev to prod dependencies in `pyproject.toml`. Run `poetry install`. **[Agent: python-backend]**
  - [x] Update `src/app/core/config.py`: add `COGNITO_URL`, `COGNITO_CLIENT_SECRET`, `COGNITO_LOGIN_REDIRECT_URL` to `CognitoSettings`. Create new `JWTSettings` class with `JWT_SECRET` (required) and `JWT_EXPIRATION_HOURS` (default: 24). Instantiate `jwt_settings` singleton. **[Agent: python-backend]**
  - [x] Update `src/app/models/user.py`: add columns `token` (Text, nullable), `oauth_access_token` (Text, nullable), `oauth_refresh_token` (Text, nullable), `oauth_id_token` (Text, nullable), `oauth_expires_at` (DateTime(timezone=True), nullable). **[Agent: postgres-database]**
  - [x] Generate Alembic migration: `make migrate-create msg="add token and oauth columns to users"`. Run `make migrate` to apply. **[Agent: postgres-database]**
  - [x] Update `.env.example` and `.env` with new variables: `COGNITO_URL`, `COGNITO_CLIENT_SECRET`, `COGNITO_LOGIN_REDIRECT_URL`, `JWT_SECRET`, `JWT_EXPIRATION_HOURS`. **[Agent: python-backend]**
  - [x] **Verify:** App starts with `make dev`. Run `make migrate` — confirm new columns exist on users table. **[Agent: python-backend]**

---

## Slice 2: User Repository & Cognito Service

_After this slice: the data access layer and Cognito HTTP client exist and are importable. No endpoints yet._

- [x] **Slice 2: User Repository & Cognito Service**
  - [x] Create `src/app/repositories/user_repository.py`: class `UserRepository` with injected `AsyncSession`. Methods: `get_by_email()`, `create()`, `update_oauth_tokens()`, `update_token()`, `get_by_id_and_token()`, `clear_token()`. **[Agent: python-backend]**
  - [x] Create `src/app/services/cognito_service.py`: class `CognitoService` using `httpx.AsyncClient`. Methods: `exchange_code_for_token(code)` (POST to Cognito /oauth2/token), `get_user_info(access_token)` (GET Cognito /oauth2/userInfo). Use 5-second timeout. Handle HTTP errors with clear messages. **[Agent: auth-security]**
  - [x] Create `src/app/schemas/auth.py`: Pydantic models — `AuthCodeRequest(code: str)`, `UserResponse(id, email, cognito_sub, role)`, `AuthResponse(user, token, expires_in)`, `MessageResponse(message: str)`. **[Agent: python-backend]**
  - [x] **Verify:** Run `PYTHONPATH=src poetry run python -c "from app.repositories.user_repository import UserRepository; from app.services.cognito_service import CognitoService; from app.schemas.auth import AuthCodeRequest, AuthResponse; print('All imports OK')"`. **[Agent: python-backend]**

---

## Slice 3: Auth Service & Token Exchange Endpoint

_After this slice: `POST /api/v1/auth` works end-to-end — exchanges code, creates/finds user, returns JWT._

- [x] **Slice 3: Auth Service & Token Exchange Endpoint**
  - [x] Create `src/app/services/auth_service.py`: class `AuthService` with injected `CognitoService` and `UserRepository`. Method `authenticate(code)` orchestrates: exchange code → get user info → find/create user → generate backend JWT with python-jose → store token → return response. **[Agent: auth-security]**
  - [x] Create `src/app/routers/auth.py`: `POST /auth` endpoint that accepts `AuthCodeRequest`, calls `AuthService.authenticate()`, returns `AuthResponse`. **[Agent: python-backend]**
  - [x] Update `src/app/core/dependencies.py`: add `get_user_repository()`, `get_cognito_service()`, `get_auth_service()` dependency providers. **[Agent: python-backend]**
  - [x] Update `src/app/main.py`: mount auth router under `/api/v1` prefix. **[Agent: python-backend]**
  - [x] **Verify:** App starts. `curl -X POST http://localhost:8000/api/v1/auth -H "Content-Type: application/json" -d '{"code":"invalid"}'` returns a 401 error (Cognito rejects the invalid code). Confirm the error message is clear. **[Agent: python-backend]**

---

## Slice 4: Auth Guard & Protected Endpoints (Validate + Logout)

_After this slice: auth guard protects routes, validate and logout work. Full auth spec is complete._

- [x] **Slice 4: Auth Guard & Protected Endpoints (Validate + Logout)**
  - [x] Update `src/app/core/dependencies.py`: add `get_current_user()` dependency — extract Bearer token, decode JWT with python-jose, look up user by ID + token in DB, return User or raise 401. **[Agent: auth-security]**
  - [x] Add `POST /api/v1/auth/validate` to auth router: protected by `get_current_user`, returns the user object. **[Agent: python-backend]**
  - [x] Add `POST /api/v1/auth/logout` to auth router: protected by `get_current_user`, calls `user_repository.clear_token()`, returns success message. **[Agent: python-backend]**
  - [x] **Verify:** Test the guard: `curl -X POST http://localhost:8000/api/v1/auth/validate` without a token returns 401. `curl -X POST http://localhost:8000/api/v1/auth/validate -H "Authorization: Bearer invalid"` returns 401. **[Agent: python-backend]**
