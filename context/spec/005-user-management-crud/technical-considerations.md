# Technical Specification: User Management (CRUD)

- **Functional Specification:** `context/spec/005-user-management-crud/functional-spec.md`
- **Status:** Completed
- **Author(s):** Pavel Boiko

---

## 1. High-Level Technical Approach

This feature extends the existing layered architecture with a new `users` router, `UserService`, and expanded `UserRepository` to support full CRUD operations on user profiles. The `users` table will be extended with profile columns (`first_name`, `last_name`, `phone_number`, `avatar_url`) and a `deleted_at` column for soft deletion.

Key architectural additions:
- **Role-based access control** via a reusable `require_role()` dependency factory (currently absent from the codebase)
- **Cognito admin operations** via boto3's `AdminDisableUser` (added to the existing `CognitoService`)
- **Soft-delete filtering** applied at the repository layer via query-level `WHERE deleted_at IS NULL` clauses
- **New Pydantic schemas** for user profile responses and pagination (separate from existing auth schemas)

No changes to the existing auth flow, Redis token storage, or health check endpoints.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1. Data Model / Database Changes

**New Alembic migration** adds columns to the `users` table:

| Column | Type | Constraints | Default |
|---|---|---|---|
| `first_name` | `String(100)` | `nullable=True` | `NULL` |
| `last_name` | `String(100)` | `nullable=True` | `NULL` |
| `phone_number` | `String(16)` | `nullable=True` | `NULL` |
| `avatar_url` | `Text` | `nullable=True` | `NULL` |
| `deleted_at` | `DateTime(timezone=True)` | `nullable=True` | `NULL` |

- `phone_number` is `String(16)` to accommodate E.164 format (`+` prefix + up to 15 digits).
- No new indexes beyond the existing `email` and `cognito_sub` unique constraints. A `deleted_at` index is not needed at this scale.
- The ORM `User` model in `src/app/models/user.py` will be updated to include these new `Mapped` columns.

### 2.2. Architecture Changes

**New files to create:**

| File | Responsibility |
|---|---|
| `src/app/routers/users.py` | User CRUD endpoints |
| `src/app/services/user_service.py` | User business logic (CRUD orchestration, permission checks) |
| `src/app/schemas/user.py` | User CRUD request/response schemas + pagination |

**Existing files to modify:**

| File | Change |
|---|---|
| `src/app/models/user.py` | Add `first_name`, `last_name`, `phone_number`, `avatar_url`, `deleted_at` columns |
| `src/app/repositories/user_repository.py` | Add methods: `list_users()`, `update()`, `soft_delete()`. Add soft-delete filtering to existing `get_by_id()` and `get_by_email()` |
| `src/app/services/cognito_service.py` | Add `admin_disable_user(cognito_sub)` method using boto3 |
| `src/app/core/dependencies.py` | Add `require_role()` factory, `get_user_service` dependency |
| `src/app/main.py` | Include the new `users` router |

### 2.3. API Contracts

All endpoints are mounted under the `/api/v1` prefix. All require a valid JWT token (`Authorization: Bearer <token>`).

#### `GET /api/v1/users`

- **Auth:** Authenticated user (any role)
- **Query params:** `offset` (int, default 0), `limit` (int, default 20, max 100), `include_deleted` (bool, default false — admin only)
- **Response (200):** `PaginatedUserResponse` — `{ items: UserProfileResponse[], total: int, offset: int, limit: int }`
- **Errors:** 401 Unauthorized

#### `GET /api/v1/users/{id}`

- **Auth:** Authenticated user (any role)
- **Path param:** `id` (UUID)
- **Query params:** `include_deleted` (bool, default false — admin only)
- **Response (200):** `UserProfileResponse`
- **Errors:** 404 Not Found, 422 Unprocessable Entity (invalid UUID)

#### `GET /api/v1/users/by-email/{email}`

- **Auth:** Authenticated user (any role)
- **Path param:** `email` (str)
- **Response (200):** `UserProfileResponse`
- **Errors:** 404 Not Found

#### `PATCH /api/v1/users/{id}`

- **Auth:** Self (own profile) or Admin (any profile)
- **Path param:** `id` (UUID)
- **Request body:** `UserUpdateRequest` — all fields optional: `first_name`, `last_name`, `phone_number`, `avatar_url`. Admin-only: `role_id`.
- **Response (200):** `UserProfileResponse`
- **Errors:** 403 Forbidden (updating another user as non-admin, or sending `email`/`role_id` as non-admin), 404 Not Found, 422 Unprocessable Entity (validation errors)

#### `DELETE /api/v1/users/{id}`

- **Auth:** Admin only (via `require_role("admin")`)
- **Path param:** `id` (UUID)
- **Response:** 204 No Content
- **Errors:** 403 Forbidden, 404 Not Found

### 2.4. Pydantic Schemas (`src/app/schemas/user.py`)

| Schema | Purpose | Key fields |
|---|---|---|
| `UserProfileResponse` | Response for all user CRUD endpoints | `id`, `email`, `first_name`, `last_name`, `phone_number`, `avatar_url`, `role` (str), `created_at`, `updated_at`, `deleted_at` (only when included). No `cognito_sub`. |
| `UserUpdateRequest` | Request body for PATCH | All fields `Optional[str] = None`. `phone_number` validated via regex for E.164. `avatar_url` validated as URL via `Pydantic.AnyHttpUrl`. |
| `PaginatedUserResponse` | Paginated list response | `items: list[UserProfileResponse]`, `total: int`, `offset: int`, `limit: int` |

The existing `UserResponse` in `schemas/auth.py` remains unchanged for auth endpoints.

### 2.5. Repository Changes (`src/app/repositories/user_repository.py`)

New/modified methods on `UserRepository`:

| Method | Signature | Behavior |
|---|---|---|
| `get_by_id` | `(user_id, include_deleted=False)` | Add `WHERE deleted_at IS NULL` filter by default |
| `get_by_email` | `(email, include_deleted=False)` | Add `WHERE deleted_at IS NULL` filter; case-insensitive via `func.lower()` |
| `list_users` | `(offset, limit, include_deleted=False)` | Paginated query with total count. Excludes soft-deleted by default |
| `update` | `(user: User, **fields)` | Set provided attributes on the model, `flush()` + `refresh()` |
| `soft_delete` | `(user: User)` | Set `deleted_at = func.now()`, `flush()` + `refresh()` |

### 2.6. Service Layer (`src/app/services/user_service.py`)

`UserService` class with constructor dependencies: `UserRepository`, `AsyncSession`, `CognitoService`.

| Method | Responsibility |
|---|---|
| `list_users(offset, limit, include_deleted, current_user)` | Enforce: `include_deleted` only allowed for admins. Delegate to repository. |
| `get_by_id(user_id, include_deleted, current_user)` | Enforce: `include_deleted` only allowed for admins. 404 if not found. |
| `get_by_email(email, include_deleted)` | Case-insensitive lookup. 404 if not found. |
| `update_user(user_id, update_data, current_user)` | Enforce: non-admins can only update own profile and only allowed fields. Validate, update, commit. |
| `delete_user(user_id, current_user)` | Enforce: admin only. Soft-delete in DB + call `cognito_service.admin_disable_user()`. Commit. |

### 2.7. Cognito Admin Integration

Add to `CognitoService` (`src/app/services/cognito_service.py`):

- New method: `async admin_disable_user(cognito_sub: str) -> None`
- Uses `boto3` client (`cognito-idp`) with `admin_disable_user(UserPoolId=..., Username=cognito_sub)`
- Wraps boto3 sync call with `asyncio.to_thread()` to avoid blocking the event loop
- Catches `ClientError` and raises `HTTPException(502)` on failure
- Requires `COGNITO_USER_POOL_ID` and `COGNITO_REGION` (already in `CognitoSettings`)

### 2.8. Role-Based Access Control (`src/app/core/dependencies.py`)

New `require_role()` factory function:

- Returns a dependency that wraps `get_current_user` and checks `user.role.name` against the provided role names
- Raises `HTTPException(403, "Insufficient permissions")` if the role does not match
- Usage: `Depends(require_role("admin"))` for admin-only endpoints, `Depends(get_current_user)` for any authenticated user (unchanged)

---

## 3. Impact and Risk Analysis

### System Dependencies

- **PostgreSQL:** Schema migration adds 5 nullable columns — backward-compatible, no data migration needed.
- **AWS Cognito:** New dependency on boto3 `AdminDisableUser` API. Requires IAM permissions: `cognito-idp:AdminDisableUser` on the user pool.
- **Redis:** No changes. Token storage and session management are unaffected.
- **Existing auth flow:** Soft-deleted users will still have valid tokens in Redis until they expire. The `get_current_user` dependency currently does not check `deleted_at`. This must be addressed — add a `deleted_at IS NULL` check in `get_current_user` to reject tokens for soft-deleted users.

### Potential Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Soft-deleted user still has active JWT in Redis | Add `deleted_at` check in `get_current_user` dependency. Optionally revoke all tokens for the user on deletion via `TokenService`. |
| boto3 `AdminDisableUser` blocks the async event loop | Wrap in `asyncio.to_thread()` to run in a thread pool. |
| Missing IAM permissions for boto3 in deployed environment | Document required IAM policy. Add descriptive error message on `ClientError`. |
| `include_deleted` query param used by non-admins to discover deleted accounts | Enforce admin-only access at the service layer; silently ignore for non-admins. |
| Case-sensitivity mismatch on email lookups | Use `func.lower()` in the repository query to ensure case-insensitive matching. |

---

## 4. Testing Strategy

Following existing patterns (`pytest-asyncio`, `TestClient` with dependency overrides):

- **Unit tests** for `UserService`: mock `UserRepository` and `CognitoService`. Test permission enforcement (self vs. admin vs. unauthorized), soft-delete behavior, field validation boundaries.
- **Unit tests** for `UserRepository`: test query filtering (soft-delete exclusion, case-insensitive email), pagination logic.
- **Route-level tests** for `users` router: use `TestClient` with overridden dependencies. Cover all endpoints, status codes, and error responses. Test self-update vs. admin-update vs. forbidden scenarios.
- **Validation tests**: E.164 phone format (valid/invalid), URL format for avatar, UUID path parameter validation.
- **Integration point**: test that `get_current_user` rejects tokens for soft-deleted users.
