"""Unit tests for TokenService with a mocked Redis client.

Each test creates a ``TokenService`` instance injected with an
``AsyncMock``-based Redis client so no real Redis connection is needed.
The mock is configured per-test to exercise each code path in isolation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

from app.services.token_service import TokenService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_TOKEN = "test-jwt"
_USER_ID = "user-123"
_EMAIL = "test@example.com"

# Pre-compute the SHA-256 hash used by the service so assertions can reference
# the same value without duplicating the hashing logic.
_TOKEN_HASH = hashlib.sha256(_TEST_TOKEN.encode()).hexdigest()
_TOKEN_KEY = f"token:{_TOKEN_HASH}"
_SESSIONS_KEY = f"sessions:{_USER_ID}"


def _make_service(redis_mock: AsyncMock) -> TokenService:
    """Construct a ``TokenService`` backed by the provided Redis mock."""
    return TokenService(redis_client=redis_mock)


def _make_redis_mock(**overrides: object) -> AsyncMock:
    """Return an ``AsyncMock`` simulating the Redis client interface.

    By default every method returns a sensible no-op value.  Pass keyword
    arguments to override specific method return values, e.g.
    ``get=AsyncMock(return_value=None)``.
    """
    mock = AsyncMock()
    mock.smembers.return_value = set()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.sadd.return_value = 1
    mock.delete.return_value = 1
    mock.srem.return_value = 1
    for attr, value in overrides.items():
        setattr(mock, attr, value)
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_store_token_saves_to_redis() -> None:
    """``store_token`` writes the hashed payload to Redis and registers the
    hash in the user's session set.
    """
    redis_mock = _make_redis_mock()
    service = _make_service(redis_mock)

    await service.store_token(_TEST_TOKEN, _USER_ID, _EMAIL)

    # The ``set`` call must use the correct key and an integer TTL.
    set_call = redis_mock.set.call_args
    assert set_call is not None
    key_arg, payload_arg = set_call.args
    assert key_arg == _TOKEN_KEY

    stored_payload: dict[str, str] = json.loads(payload_arg)
    assert stored_payload["user_id"] == _USER_ID
    assert stored_payload["email"] == _EMAIL
    # ``created_at`` must be present and parseable as an ISO 8601 datetime.
    assert "created_at" in stored_payload
    datetime.fromisoformat(stored_payload["created_at"])  # raises if malformed

    # TTL keyword argument must be set.
    assert "ex" in set_call.kwargs
    assert isinstance(set_call.kwargs["ex"], int)
    assert set_call.kwargs["ex"] > 0

    # The token hash must be added to the session set.
    redis_mock.sadd.assert_awaited_once_with(_SESSIONS_KEY, _TOKEN_HASH)


async def test_validate_token_returns_payload() -> None:
    """``validate_token`` returns the stored payload dict when the token is
    present in Redis.
    """
    stored_data = {
        "user_id": _USER_ID,
        "email": _EMAIL,
        "created_at": datetime.now(UTC).isoformat(),
    }
    redis_mock = _make_redis_mock(get=AsyncMock(return_value=json.dumps(stored_data)))
    service = _make_service(redis_mock)

    result = await service.validate_token(_TEST_TOKEN)

    assert result is not None
    assert result["user_id"] == _USER_ID
    assert result["email"] == _EMAIL
    assert "created_at" in result

    # Verify the correct key was looked up.
    redis_mock.get.assert_awaited_once_with(_TOKEN_KEY)


async def test_validate_token_returns_none_for_missing() -> None:
    """``validate_token`` returns ``None`` when the token is absent from
    Redis (expired, revoked, or never stored).
    """
    redis_mock = _make_redis_mock(get=AsyncMock(return_value=None))
    service = _make_service(redis_mock)

    result = await service.validate_token(_TEST_TOKEN)

    assert result is None
    redis_mock.get.assert_awaited_once_with(_TOKEN_KEY)


async def test_revoke_token_deletes_from_redis() -> None:
    """``revoke_token`` deletes the token key and removes the hash from the
    user's session set.
    """
    redis_mock = _make_redis_mock()
    service = _make_service(redis_mock)

    await service.revoke_token(_TEST_TOKEN, _USER_ID)

    redis_mock.delete.assert_awaited_once_with(_TOKEN_KEY)
    redis_mock.srem.assert_awaited_once_with(_SESSIONS_KEY, _TOKEN_HASH)


async def test_session_limit_evicts_oldest() -> None:
    """When a user already has ``REDIS_MAX_SESSIONS`` (3) active sessions,
    ``store_token`` must evict the oldest one before persisting the new token.
    """
    # Build three existing session hashes with distinct creation timestamps.
    # The service evicts sessions whose ``created_at`` is smallest (oldest).
    oldest_hash = hashlib.sha256(b"oldest-token").hexdigest()
    middle_hash = hashlib.sha256(b"middle-token").hexdigest()
    newest_hash = hashlib.sha256(b"newest-token").hexdigest()

    oldest_payload = json.dumps(
        {
            "user_id": _USER_ID,
            "email": _EMAIL,
            "created_at": "2024-01-01T00:00:00+00:00",
        }
    )
    middle_payload = json.dumps(
        {
            "user_id": _USER_ID,
            "email": _EMAIL,
            "created_at": "2024-06-01T00:00:00+00:00",
        }
    )
    newest_payload = json.dumps(
        {
            "user_id": _USER_ID,
            "email": _EMAIL,
            "created_at": "2024-12-01T00:00:00+00:00",
        }
    )

    # Map each token key to its payload so the mock can return the right value.
    payload_by_key: dict[str, str] = {
        f"token:{oldest_hash}": oldest_payload,
        f"token:{middle_hash}": middle_payload,
        f"token:{newest_hash}": newest_payload,
    }

    async def fake_get(key: str) -> str | None:
        # The new token's key is not in the map yet — return None for it.
        return payload_by_key.get(key)

    redis_mock = _make_redis_mock(
        smembers=AsyncMock(return_value={oldest_hash, middle_hash, newest_hash}),
        get=AsyncMock(side_effect=fake_get),
    )
    service = _make_service(redis_mock)

    await service.store_token(_TEST_TOKEN, _USER_ID, _EMAIL)

    # The oldest session must have been evicted: its token key deleted and its
    # hash removed from the session set.
    oldest_token_key = f"token:{oldest_hash}"
    redis_mock.delete.assert_any_await(oldest_token_key)
    redis_mock.srem.assert_any_await(_SESSIONS_KEY, oldest_hash)

    # The middle and newest sessions must NOT have been evicted.
    delete_calls = [c.args[0] for c in redis_mock.delete.call_args_list]
    assert f"token:{middle_hash}" not in delete_calls
    assert f"token:{newest_hash}" not in delete_calls


async def test_store_token_raises_503_on_redis_error() -> None:
    """``store_token`` must raise ``HTTPException(503)`` when Redis raises a
    ``ConnectionError``, shielding the caller from raw infrastructure errors.
    """
    # Raise on ``set`` — the first Redis write attempted after the session
    # limit check succeeds.
    redis_mock = _make_redis_mock(
        set=AsyncMock(side_effect=RedisConnectionError("connection refused"))
    )
    service = _make_service(redis_mock)

    with pytest.raises(HTTPException) as exc_info:
        await service.store_token(_TEST_TOKEN, _USER_ID, _EMAIL)

    assert exc_info.value.status_code == 503
    assert "unavailable" in exc_info.value.detail.lower()
