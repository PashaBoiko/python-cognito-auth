from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import jwt_settings, redis_settings

logger = logging.getLogger(__name__)

# Redis key prefixes that define the storage layout for token data and
# per-user session tracking.
_TOKEN_KEY_PREFIX = "token:"
_SESSIONS_KEY_PREFIX = "sessions:"


class TokenService:
    """Handles storage and lifecycle management of application JWTs in Redis.

    Tokens are stored under ``token:{sha256_hash}`` with a JSON payload
    containing identity fields.  Each user's active session hashes are
    tracked in a Redis Set under ``sessions:{user_id}``, enabling efficient
    per-user session enumeration and future eviction logic.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def store_token(self, token: str, user_id: str, email: str) -> None:
        """Persist a JWT in Redis and register it in the user's session set.

        The raw token string is never stored; only its SHA-256 digest is used
        as a key so that the token value cannot be reconstructed from the
        cache in the event of a Redis exposure.

        The key expires after ``JWT_EXPIRATION_HOURS * 3600`` seconds, which
        matches the token's own expiry so Redis reclaims memory automatically.

        Args:
            token: The signed JWT string issued to the user.
            user_id: The UUID string identifying the token owner.
            email: The email address associated with the token owner.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        token_key = f"{_TOKEN_KEY_PREFIX}{token_hash}"
        sessions_key = f"{_SESSIONS_KEY_PREFIX}{user_id}"

        # TTL mirrors the JWT's own validity window so the Redis entry expires
        # at the same time the token becomes invalid.
        ttl_seconds = jwt_settings.JWT_EXPIRATION_HOURS * 3600

        token_payload = json.dumps(
            {
                "user_id": user_id,
                "email": email,
                # ISO 8601 with explicit UTC offset for unambiguous parsing by
                # any consumer of this data.
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

        try:
            await self._enforce_session_limit(user_id)
            await self._redis.set(token_key, token_payload, ex=ttl_seconds)
            await self._redis.sadd(sessions_key, token_hash)  # type: ignore[misc]
        except (RedisConnectionError, RedisTimeoutError) as err:
            logger.error("Redis unavailable during store_token: %s", err)
            raise HTTPException(
                status_code=503,
                detail="Redis is unavailable",
            ) from err

        logger.debug(
            "Stored token for user_id=%s token_key=%s ttl=%d",
            user_id,
            token_key,
            ttl_seconds,
        )

    async def _enforce_session_limit(self, user_id: str) -> None:
        """Evict the oldest session(s) if the user has reached the max session count.

        Iterates the ``sessions:{user_id}`` Redis Set, discards hashes whose
        ``token:`` key has already expired, then evicts the oldest remaining
        sessions (sorted by ``created_at``) until there is room for exactly one
        more new session.

        Args:
            user_id: The UUID string identifying the user whose session count
                should be checked and, if necessary, reduced.
        """
        sessions_key = f"{_SESSIONS_KEY_PREFIX}{user_id}"
        max_sessions = redis_settings.REDIS_MAX_SESSIONS

        # Retrieve all token hashes currently tracked for this user.
        all_hashes: set[str] = await self._redis.smembers(sessions_key)  # type: ignore[misc]

        # Walk each hash: drop stale entries whose token key has already
        # expired from Redis, and collect the rest with their creation time
        # so we can sort by age below.
        active_sessions: list[tuple[str, str]] = []  # (hash, created_at)
        for token_hash in all_hashes:
            token_key = f"{_TOKEN_KEY_PREFIX}{token_hash}"
            raw_payload = await self._redis.get(token_key)
            if raw_payload is None:
                # Token has expired; remove the now-stale hash from the set
                # so it does not skew the session count.
                await self._redis.srem(sessions_key, token_hash)  # type: ignore[misc]
            else:
                payload = json.loads(raw_payload)
                active_sessions.append((token_hash, payload.get("created_at", "")))

        # Only evict when we are at or over the limit — sort ascending by
        # creation timestamp so the oldest sessions are removed first.
        if len(active_sessions) >= max_sessions:
            active_sessions.sort(key=lambda x: x[1])
            evict_count = len(active_sessions) - max_sessions + 1
            sessions_to_evict = active_sessions[:evict_count]

            for token_hash, _ in sessions_to_evict:
                token_key = f"{_TOKEN_KEY_PREFIX}{token_hash}"
                await self._redis.delete(token_key)
                await self._redis.srem(sessions_key, token_hash)  # type: ignore[misc]
                logger.debug(
                    "Evicted oldest session token_key=%s for user_id=%s",
                    token_key,
                    user_id,
                )

    async def validate_token(self, token: str) -> dict[str, str] | None:
        """Check if a token exists in Redis and return its stored data.

        The raw token is hashed before lookup so the plaintext value is never
        used as a cache key.  A ``None`` return value means the token was not
        found — either it never existed, it has expired, or it was revoked.

        Args:
            token: The signed JWT string to validate.

        Returns:
            A dictionary with ``user_id``, ``email``, and ``created_at`` keys
            if the token is active, otherwise ``None``.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        token_key = f"{_TOKEN_KEY_PREFIX}{token_hash}"

        try:
            raw_payload = await self._redis.get(token_key)
        except (RedisConnectionError, RedisTimeoutError) as err:
            logger.error("Redis unavailable during validate_token: %s", err)
            raise HTTPException(
                status_code=503,
                detail="Redis is unavailable",
            ) from err

        if raw_payload is None:
            logger.debug("Token not found in Redis token_key=%s", token_key)
            return None

        payload: dict[str, str] = json.loads(raw_payload)
        logger.debug(
            "Token validated for user_id=%s token_key=%s",
            payload.get("user_id"),
            token_key,
        )
        return payload

    async def revoke_token(self, token: str, user_id: str) -> None:
        """Remove a token from Redis and the user's session set.

        The raw token is hashed before deletion so the plaintext value is
        never used as a cache key.  After this call the token will no longer
        be found by ``validate_token``, effectively invalidating the session.

        Args:
            token: The signed JWT string to revoke.
            user_id: The UUID string of the token owner.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        token_key = f"{_TOKEN_KEY_PREFIX}{token_hash}"
        sessions_key = f"{_SESSIONS_KEY_PREFIX}{user_id}"

        try:
            await self._redis.delete(token_key)
            await self._redis.srem(sessions_key, token_hash)  # type: ignore[misc]
        except (RedisConnectionError, RedisTimeoutError) as err:
            logger.error("Redis unavailable during revoke_token: %s", err)
            raise HTTPException(
                status_code=503,
                detail="Redis is unavailable",
            ) from err

        logger.debug("Revoked token for user_id=%s token_key=%s", user_id, token_key)
