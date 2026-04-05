# Functional Specification: Redis-Based Token Storage for Multi-Session Support

- **Roadmap Item:** Enhancement to Phase 2 — Core Auth (Token Storage & Session Management)
- **Status:** Completed
- **Author:** AWOS

---

## 1. Overview and Rationale (The "Why")

Currently, the auth service stores a single application JWT in the `token` column of the `users` table in PostgreSQL. This design has two limitations:

1. **Single-session only** — Each new login overwrites the previous token, so a user logging in from their phone automatically logs out their laptop session. This creates friction for users who work across multiple devices.
2. **Performance** — Every token validation request (`POST /api/v1/auth/validate`) queries PostgreSQL, adding unnecessary latency to a high-frequency operation. The product definition targets sub-200ms response times on auth endpoints.

By moving token storage to Redis, we solve both problems: Redis supports multiple keys per user (enabling concurrent sessions) and provides in-memory lookups that are significantly faster than database queries. Redis also natively supports TTL (time-to-live), which means expired tokens are automatically cleaned up without any application-side garbage collection.

**Success criteria:**
- Users can maintain up to 3 concurrent sessions across devices.
- Token validation no longer hits PostgreSQL.
- Expired tokens are automatically removed by Redis TTL.
- The `token` column is removed from the `users` table.

---

## 2. Functional Requirements (The "What")

### 2.1 Multi-Session Token Storage

- When a user logs in via `POST /api/v1/auth`, the issued JWT is stored in Redis with a TTL matching the JWT expiration (24 hours by default, driven by `JWT_EXPIRATION_HOURS`).
- Each token is stored as its own Redis key, enabling multiple active tokens per user.
- **Acceptance Criteria:**
  - [x]After a successful login, the token exists in Redis with the correct TTL.
  - [x]A user can log in from a second device and both sessions remain valid.
  - [x]A user can have up to 3 concurrent active sessions.

### 2.2 Session Limit Enforcement (Max 3 Sessions)

- The system tracks all active sessions for a given user.
- When a user logs in and already has 3 active sessions, the **oldest session** is silently revoked (its token key is deleted from Redis) and the new login succeeds normally.
- No warning or notification is shown to the user.
- **Acceptance Criteria:**
  - [x]A user with 3 active sessions can log in again successfully.
  - [x]After the 4th login, the oldest of the original 3 sessions is no longer valid.
  - [x]The new (4th) login response is identical to a normal login response — no error, no extra message.

### 2.3 Token Validation via Redis

- `POST /api/v1/auth/validate` looks up the Bearer token in Redis instead of PostgreSQL.
- If the token exists in Redis, the user is authenticated. If not, the request returns 401.
- **Acceptance Criteria:**
  - [x]A valid, non-expired token returns 200 with the user profile.
  - [x]An expired or revoked token returns 401.
  - [x]PostgreSQL is not queried during token validation.

### 2.4 Logout (Current Session Only)

- `POST /api/v1/auth/logout` deletes the specific token from Redis, ending only the current session.
- Other active sessions for the same user remain valid.
- **Acceptance Criteria:**
  - [x]After logout, the used token returns 401 on subsequent validation.
  - [x]Other active sessions for the same user continue to work.

### 2.5 Automatic Token Expiry

- Redis TTL is set to match `JWT_EXPIRATION_HOURS` (default 24 hours) when the token is stored.
- When the TTL expires, Redis automatically deletes the key. No application-side cleanup is needed.
- **Acceptance Criteria:**
  - [x]A token stored with a 24h TTL is no longer retrievable from Redis after 24 hours.
  - [x]No background job or cron is required for token cleanup.

### 2.6 Redis Unavailability

- If Redis is unreachable, all token-dependent endpoints (`/auth`, `/auth/validate`, `/auth/logout`) return **503 Service Unavailable**.
- The `/health` endpoint reports Redis connectivity status alongside the database status.
- **Acceptance Criteria:**
  - [x]When Redis is down, `POST /api/v1/auth` returns 503.
  - [x]When Redis is down, `POST /api/v1/auth/validate` returns 503.
  - [x]When Redis is down, `POST /api/v1/auth/logout` returns 503.
  - [x]`GET /health` reports Redis status as "connected" or "disconnected".

### 2.7 Remove Token Column from PostgreSQL

- The `token` column is removed from the `users` table via an Alembic migration.
- All token-related operations in `UserRepository` (`update_token`, `clear_token`, `get_by_id_and_token`) are replaced by Redis operations.
- **Acceptance Criteria:**
  - [x]The `token` column no longer exists in the `users` table.
  - [x]No application code references the `token` column.

---

## 3. Scope and Boundaries

### In-Scope

- Adding Redis as a token store with TTL support.
- Supporting up to 3 concurrent sessions per user with oldest-session eviction.
- Single-session logout via `POST /api/v1/auth/logout`.
- Returning 503 when Redis is unavailable.
- Adding Redis status to the `/health` endpoint.
- Removing the `token` column from the `users` table.
- Redis connection configuration via environment variables.

### Out-of-Scope

- **Logout all sessions endpoint** — separate future enhancement.
- **User Lookup endpoints** (`GET /users/{id}`, `GET /users/by-email/{email}`) — Phase 3 roadmap item.
- **Role Management** (`GET /roles`, `POST /roles`, role assignment) — Phase 3 roadmap item.
- **Sliding TTL / token refresh** — tokens have a fixed TTL matching JWT expiration.
- **Redis Sentinel / Cluster configuration** — infrastructure concern, not application scope.
- **Session listing UI** — no endpoint to list a user's active sessions.
