# Tasks: Redis-Based Token Storage for Multi-Session Support

---

- [x] **Slice 1: Redis Connection & Health Check**
  - [x] Add `redis:7-alpine` service to `docker-compose.yml` with healthcheck. Update `app` service `depends_on` and add `REDIS_URL` env var. **[Agent: aws-infra]**
  - [x] Add `redis[hiredis]` to `pyproject.toml` dependencies. **[Agent: python-backend]**
  - [x] Add `RedisSettings` class to `src/app/core/config.py` with `REDIS_URL` (required) and `REDIS_MAX_SESSIONS` (default 3). Add `redis_settings` module-level singleton. **[Agent: python-backend]**
  - [x] Create `src/app/core/redis.py` with async Redis client singleton and FastAPI lifespan lifecycle (connect on startup, close on shutdown). **[Agent: redis-cache]**
  - [x] Add `redis: str` field to `HealthResponse` schema in `src/app/schemas/health.py`. **[Agent: python-backend]**
  - [x] Update `src/app/routers/health.py` to inject Redis client and add a `PING` probe alongside the DB probe. Report `redis: "connected"` or `"disconnected"`. **[Agent: python-backend]**
  - [x] Add `REDIS_URL` to `.env.example` (if exists) or document required env var. **[Agent: python-backend]**
  - [x] **Verify:** Start the app with `docker compose up`. Call `GET /health` and confirm the response includes `"redis": "connected"`. Stop Redis container, call `/health` again, confirm `"redis": "disconnected"`. **[Agent: python-backend]**

- [x] **Slice 2: Token Storage in Redis on Login**
  - [x] Create `src/app/services/token_service.py` with `store_token` method: SHA-256 hash the JWT, store `token:{hash}` key in Redis with user data and TTL, add hash to `sessions:{user_id}` set. **[Agent: redis-cache]**
  - [x] Add `get_token_service` dependency in `src/app/core/dependencies.py` that injects the Redis client. **[Agent: python-backend]**
  - [x] Update `src/app/services/auth_service.py` to inject `TokenService` and call `store_token` after issuing the JWT (replacing `user_repository.update_token`). **[Agent: python-backend]**
  - [x] **Verify:** Log in via `POST /api/v1/auth` with a valid Cognito code. Confirm the response returns a token. Use `redis-cli KEYS "token:*"` to confirm the token key exists with correct TTL. **[Agent: python-backend]**

- [x] **Slice 3: Token Validation via Redis**
  - [x] Add `validate_token` method to `TokenService`: SHA-256 hash the presented JWT, check if `token:{hash}` exists in Redis, return user data if found. **[Agent: redis-cache]**
  - [x] Update `get_current_user` in `src/app/core/dependencies.py` to use `TokenService.validate_token` instead of `user_repository.get_by_id_and_token`. Still query PostgreSQL for the full `User` object by ID. **[Agent: python-backend]**
  - [x] **Verify:** Log in, then call `POST /api/v1/auth/validate` with the Bearer token. Confirm 200 with user data. Try with an invalid token — confirm 401. **[Agent: python-backend]**

- [x] **Slice 4: Logout via Redis**
  - [x] Add `revoke_token` method to `TokenService`: SHA-256 hash the JWT, delete `token:{hash}` from Redis, remove hash from `sessions:{user_id}` set. **[Agent: redis-cache]**
  - [x] Update `src/app/routers/auth.py` logout endpoint to inject `TokenService` and call `revoke_token` instead of `user_repository.clear_token`. **[Agent: python-backend]**
  - [x] **Verify:** Log in, confirm validate works, then call `POST /api/v1/auth/logout`. Confirm validate now returns 401 with the same token. **[Agent: python-backend]**

- [x] **Slice 5: Session Limit Enforcement**
  - [x] Add `_enforce_session_limit` private method to `TokenService`: get all hashes from `sessions:{user_id}`, filter out expired (check `EXISTS`), if 3+ active remain, delete the oldest by `created_at` timestamp and remove from set. **[Agent: redis-cache]**
  - [x] Call `_enforce_session_limit` inside `store_token` before adding the new token. **[Agent: redis-cache]**
  - [x] **Verify:** Log in 4 times with the same user. Confirm the first token is now invalid (401 on validate) while tokens 2, 3, 4 remain valid. **[Agent: python-backend]**

- [x] **Slice 6: Redis Unavailability Handling**
  - [x] Add error handling in `TokenService` methods to catch Redis connection errors and raise `HTTPException(503)`. **[Agent: redis-cache]**
  - [x] Ensure `POST /api/v1/auth`, `/auth/validate`, and `/auth/logout` all return 503 when Redis is unreachable. **[Agent: python-backend]**
  - [x] **Verify:** Stop Redis container. Call each auth endpoint and confirm 503 responses. Restart Redis, confirm endpoints work again. **[Agent: python-backend]**

- [x] **Slice 7: Database Cleanup**
  - [x] Remove `token` field from `User` model in `src/app/models/user.py`. **[Agent: postgres-database]**
  - [x] Remove `update_token`, `clear_token`, `get_by_id_and_token` methods from `src/app/repositories/user_repository.py`. **[Agent: postgres-database]**
  - [x] Create Alembic migration to drop the `token` column from the `users` table. **[Agent: postgres-database]**
  - [x] **Verify:** Run `alembic upgrade head`. Start the app. Confirm full login → validate → logout flow works without the token column. **[Agent: python-backend]**

- [x] **Slice 8: Tests & CI**
  - [x] Write unit tests for `TokenService` (store, validate, revoke, session limit) with mocked Redis client. **[Agent: python-backend]**
  - [x] Update existing tests in `tests/test_auth.py` to mock `TokenService` instead of DB token methods. **[Agent: python-backend]**
  - [x] Add `redis:7-alpine` service to `.github/workflows/ci.yml` with `REDIS_URL` env var. **[Agent: aws-infra]**
  - [x] **Verify:** Run `poetry run ruff check src/ && poetry run ruff format --check src/ && poetry run mypy src/ && poetry run pytest -v` — all must pass. **[Agent: python-backend]**
