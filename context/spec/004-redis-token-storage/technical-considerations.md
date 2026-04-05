# Technical Specification: Redis-Based Token Storage for Multi-Session Support

- **Functional Specification:** `context/spec/004-redis-token-storage/functional-spec.md`
- **Status:** Completed
- **Author(s):** AWOS

---

## 1. High-Level Technical Approach

Introduce Redis as the dedicated token store, replacing the PostgreSQL `token` column. A new `redis-py[hiredis]` async client will be managed as a module-level singleton in `src/app/core/redis.py`, following the same pattern as the SQLAlchemy engine in `database.py`. Tokens will be stored as SHA-256 hashed keys with a TTL matching the JWT expiration. A per-user session set will track active tokens and enforce the 3-session limit with oldest-eviction. The `get_current_user` dependency will validate tokens against Redis, then query PostgreSQL only for the full User object. The `token` column will be removed from the `users` table via Alembic migration; OAuth token columns are retained.

---

## 2. Proposed Solution & Implementation Plan

### 2.1 Architecture Changes

| Component | Change |
|---|---|
| New module: `src/app/core/redis.py` | Module-level async Redis client singleton, `get_redis_client` dependency, lifecycle management via FastAPI lifespan |
| New settings: `RedisSettings` in `config.py` | `REDIS_URL` (required), `REDIS_MAX_SESSIONS` (default 3) |
| New service: `src/app/services/token_service.py` | Encapsulates all Redis token operations (store, validate, revoke, evict) |
| Modified: `dependencies.py` | `get_current_user` checks Redis instead of `user_repository.get_by_id_and_token` |
| Modified: `auth_service.py` | Uses `TokenService` instead of `user_repository.update_token` |
| Modified: `health.py` | Adds Redis ping probe |
| Removed from `user_repository.py` | `update_token`, `clear_token`, `get_by_id_and_token` methods |

### 2.2 Redis Key Structure

| Key Pattern | Value | TTL |
|---|---|---|
| `token:{sha256_hash}` | JSON: `{"user_id": "uuid", "email": "string", "created_at": "iso8601"}` | `JWT_EXPIRATION_HOURS * 3600` seconds |
| `sessions:{user_id}` | Redis Set of SHA-256 token hashes | No TTL (cleaned on login/logout) |

**Session limit enforcement flow (on login):**
1. Hash the new JWT with SHA-256
2. `SMEMBERS sessions:{user_id}` — get all active token hashes
3. For each hash, check if `token:{hash}` still exists (filters out expired)
4. If 3 or more active tokens remain, delete the oldest (by `created_at` timestamp in token value) and `SREM` it from the set
5. `SET token:{new_hash}` with TTL and `SADD sessions:{user_id}`

### 2.3 Data Model Changes

**Alembic migration — remove `token` column:**

| Table | Column | Action |
|---|---|---|
| `users` | `token` | DROP |

OAuth columns (`oauth_access_token`, `oauth_refresh_token`, `oauth_id_token`, `oauth_expires_at`) are **retained** — they serve the Cognito relationship, not session management.

### 2.4 API Contracts

No API changes. All three endpoints keep the same request/response shapes:

| Endpoint | Behavior Change |
|---|---|
| `POST /api/v1/auth` | Token stored in Redis instead of DB. Session limit enforced. |
| `POST /api/v1/auth/validate` | Token checked in Redis instead of DB. Still returns `UserResponse` from PostgreSQL. |
| `POST /api/v1/auth/logout` | Token deleted from Redis instead of DB. |
| `GET /health` | Response adds `redis: "connected" | "disconnected"` field. |

### 2.5 Configuration

New `RedisSettings` class in `config.py`:

| Env Variable | Type | Default | Purpose |
|---|---|---|---|
| `REDIS_URL` | `str` (required) | — | Redis connection string, e.g. `redis://localhost:6379` |
| `REDIS_MAX_SESSIONS` | `int` | `3` | Maximum concurrent sessions per user |

### 2.6 New/Modified Files

| File | Responsibility |
|---|---|
| `src/app/core/redis.py` (new) | Redis client singleton, connection lifecycle, `get_redis_client` dependency |
| `src/app/services/token_service.py` (new) | `store_token`, `validate_token`, `revoke_token`, `_enforce_session_limit` |
| `src/app/core/config.py` | Add `RedisSettings` + `redis_settings` singleton |
| `src/app/core/dependencies.py` | Inject `TokenService`, update `get_current_user` |
| `src/app/services/auth_service.py` | Replace `user_repository.update_token` with `token_service.store_token` |
| `src/app/routers/auth.py` | Inject `TokenService` for logout |
| `src/app/routers/health.py` | Add Redis ping probe |
| `src/app/schemas/health.py` | Add `redis: str` field |
| `src/app/models/user.py` | Remove `token` column |
| `src/app/repositories/user_repository.py` | Remove `update_token`, `clear_token`, `get_by_id_and_token` |
| `pyproject.toml` | Add `redis[hiredis]` dependency |
| `docker-compose.yml` | Add `redis:7-alpine` service |
| `alembic/versions/` | New migration to drop `token` column |

---

## 3. Impact and Risk Analysis

### System Dependencies

- **New infrastructure dependency:** Redis must be running and reachable. Docker Compose updated accordingly.
- **CI pipeline:** The GitHub Actions workflow needs a Redis service container for tests.
- **Deployment:** ECS/Fargate tasks will need access to a Redis instance (ElastiCache recommended for production).

### Potential Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Redis goes down | All auth operations fail (503) | Health check exposes status; monitoring/alerts on Redis availability |
| Session set grows stale (expired token hashes remain in set) | Set accumulates dead entries | Clean stale entries on every login by checking `EXISTS token:{hash}` before counting |
| Race condition on session eviction | Could briefly exceed 3 sessions | Acceptable — eventual consistency; next login will clean up |
| Migration removes token column while old code is running | Broken deployments | Deploy new code first (reads from Redis), then run migration |

---

## 4. Testing Strategy

- **Unit tests:** Mock Redis client, test `TokenService` methods (store, validate, revoke, session limit enforcement).
- **Unit tests:** Test `get_current_user` with mocked `TokenService` — valid token, expired token, revoked token.
- **Integration tests:** Use a real Redis instance (via CI service container) to test TTL behavior and session eviction.
- **Health check tests:** Mock Redis ping to test connected/disconnected reporting.
- **Migration test:** Verify Alembic migration runs cleanly (up and down).
- **CI update:** Add `redis:7-alpine` service to `.github/workflows/ci.yml` with `REDIS_URL` env var.
