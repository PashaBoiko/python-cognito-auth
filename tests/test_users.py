from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db_session, get_user_service
from app.core.redis import get_redis_client
from app.main import create_app


@pytest.fixture()
def app():
    application = create_app()

    async def override_db_session():
        yield AsyncMock()

    async def override_redis_client():
        yield AsyncMock()

    application.dependency_overrides[get_db_session] = override_db_session
    application.dependency_overrides[get_redis_client] = override_redis_client
    return application


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def fake_current_user():
    """A minimal authenticated user suitable for passing the get_current_user guard."""
    return SimpleNamespace(
        id=uuid4(),
        email="auth@example.com",
        cognito_sub="cognito-sub-auth",
        role=SimpleNamespace(name="admin"),
    )


@pytest.fixture()
def fake_target_user():
    """A fully-populated User-like object that get_by_id returns on success."""
    now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        email="target@example.com",
        first_name="Ada",
        last_name="Lovelace",
        phone_number="+10000000000",
        avatar_url="https://example.com/avatar.png",
        # role is expected as an object with a ``name`` attribute by UserProfileResponse
        role=SimpleNamespace(name="user"),
        created_at=now,
        updated_at=now,
        deleted_at=None,
        # cognito_sub exists on the ORM object but must NOT appear in the response
        cognito_sub="cognito-sub-target",
    )


def test_get_user_by_id_valid_uuid_returns_200_with_profile(
    app, client, fake_current_user, fake_target_user
):
    """A valid UUID for an existing user returns 200 and the expected profile fields."""
    # Override get_current_user so no real JWT verification is performed.
    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    # Build a mock UserService whose get_by_id coroutine returns the fake target user.
    mock_user_service = AsyncMock()
    mock_user_service.get_by_id = AsyncMock(return_value=fake_target_user)

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.get(f"/api/v1/users/{fake_target_user.id}")

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == str(fake_target_user.id)
    assert data["email"] == fake_target_user.email
    assert data["first_name"] == fake_target_user.first_name
    assert data["last_name"] == fake_target_user.last_name
    assert data["phone_number"] == fake_target_user.phone_number
    assert data["avatar_url"] == fake_target_user.avatar_url
    # role must be serialised as a plain string (coerced from the Role ORM object)
    assert data["role"] == "user"
    assert "created_at" in data
    assert "updated_at" in data
    # cognito_sub is an internal field and must never be exposed to API consumers
    assert "cognito_sub" not in data


def test_get_user_by_id_nonexistent_uuid_returns_404(app, client, fake_current_user):
    """A valid UUID that matches no user causes UserService to raise 404."""
    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    # Simulate UserService raising HTTPException(404) when the user is not found.
    mock_user_service = AsyncMock()
    mock_user_service.get_by_id = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="User not found")
    )

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    nonexistent_id = uuid4()
    response = client.get(f"/api/v1/users/{nonexistent_id}")

    assert response.status_code == 404


def test_get_user_by_id_invalid_uuid_format_returns_422(app, client, fake_current_user):
    """A path segment that is not a valid UUID triggers FastAPI request validation (422)."""
    # get_current_user is overridden so the test does not depend on auth logic,
    # but FastAPI will reject the request before even calling the dependency
    # because the UUID path parameter fails Pydantic coercion.
    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    response = client.get("/api/v1/users/not-a-uuid")

    assert response.status_code == 422


def test_list_users_default_pagination_returns_200_with_paginated_response(
    app, client, fake_current_user, fake_target_user
):
    """GET /api/v1/users with no query params returns 200 and a paginated envelope."""
    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    mock_user_service = AsyncMock()
    # list_users returns a (users, total_count) tuple
    mock_user_service.list_users = AsyncMock(return_value=([fake_target_user], 1))

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.get("/api/v1/users")

    assert response.status_code == 200

    data = response.json()
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1
    assert data["total"] == 1
    # Default values must be reflected back in the response envelope
    assert data["offset"] == 0
    assert data["limit"] == 20


def test_list_users_custom_offset_and_limit_are_forwarded_to_service(
    app, client, fake_current_user, fake_target_user
):
    """Custom offset and limit query params are passed through to list_users and mirrored in the response."""
    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    mock_user_service = AsyncMock()
    mock_user_service.list_users = AsyncMock(return_value=([fake_target_user], 1))

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.get("/api/v1/users?offset=10&limit=5")

    assert response.status_code == 200

    # Verify the service layer received the exact pagination parameters from the request
    mock_user_service.list_users.assert_awaited_once_with(
        offset=10,
        limit=5,
        include_deleted=False,
        current_user=fake_current_user,
    )

    data = response.json()
    assert data["offset"] == 10
    assert data["limit"] == 5


def test_list_users_without_authentication_returns_401(app, client):
    """GET /api/v1/users with no Authorization header is rejected with 401 before any service call."""
    # Intentionally do NOT override get_current_user so the real dependency runs
    # and raises 401 because no Bearer token is present in the request.
    response = client.get("/api/v1/users")

    assert response.status_code == 401


def test_patch_user_self_update_valid_fields_returns_200(
    app, client, fake_current_user, fake_target_user
):
    """PATCH /api/v1/users/{id} with valid fields for the authenticated user's own id returns 200."""
    # Make the target user share the same id as the authenticated user so the
    # service's ownership check passes.
    fake_target_user.id = fake_current_user.id
    fake_target_user.first_name = "Updated"

    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    mock_user_service = AsyncMock()
    mock_user_service.update_user = AsyncMock(return_value=fake_target_user)

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.patch(
        f"/api/v1/users/{fake_current_user.id}",
        json={"first_name": "Updated"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["first_name"] == "Updated"
    assert data["id"] == str(fake_current_user.id)


def test_patch_user_updating_another_user_returns_403(
    app, client, fake_current_user, fake_target_user
):
    """PATCH /api/v1/users/{id} where the id belongs to a different user returns 403."""
    # fake_target_user.id differs from fake_current_user.id by fixture default,
    # so the request naturally targets another user.
    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    mock_user_service = AsyncMock()
    mock_user_service.update_user = AsyncMock(
        side_effect=HTTPException(
            status_code=403,
            detail="You can only update your own profile",
        )
    )

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.patch(
        f"/api/v1/users/{fake_target_user.id}",
        json={"first_name": "Hacker"},
    )

    assert response.status_code == 403


def test_patch_user_invalid_phone_number_returns_422(app, client, fake_current_user):
    """PATCH /api/v1/users/{id} with a phone_number that violates E.164 is rejected by Pydantic with 422."""
    # Auth must pass so the request reaches Pydantic body validation.
    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    # Override the service as well to avoid any real DB calls, even though
    # validation fails before the service is ever invoked.
    mock_user_service = AsyncMock()
    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.patch(
        f"/api/v1/users/{fake_current_user.id}",
        json={"phone_number": "invalid"},
    )

    assert response.status_code == 422


def test_patch_user_invalid_avatar_url_returns_422(app, client, fake_current_user):
    """PATCH /api/v1/users/{id} with an avatar_url that is not a valid HTTP URL is rejected by Pydantic with 422."""
    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    mock_user_service = AsyncMock()
    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.patch(
        f"/api/v1/users/{fake_current_user.id}",
        json={"avatar_url": "not-a-url"},
    )

    assert response.status_code == 422


def test_patch_user_sending_email_field_returns_403(app, client, fake_current_user):
    """PATCH /api/v1/users/{id} with an email field is rejected by the service with 403."""
    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    mock_user_service = AsyncMock()
    mock_user_service.update_user = AsyncMock(
        side_effect=HTTPException(
            status_code=403,
            detail="You are not allowed to update the following fields: email",
        )
    )

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.patch(
        f"/api/v1/users/{fake_current_user.id}",
        json={"email": "new@example.com"},
    )

    assert response.status_code == 403


def test_patch_user_soft_deleted_user_returns_404(app, client, fake_current_user):
    """PATCH /api/v1/users/{id} for a soft-deleted user returns 404."""
    app.dependency_overrides[get_current_user] = lambda: fake_current_user

    mock_user_service = AsyncMock()
    mock_user_service.update_user = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="User not found")
    )

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.patch(
        f"/api/v1/users/{fake_current_user.id}",
        json={"first_name": "Ghost"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Slice 5 — Admin capabilities
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_admin_user():
    """An authenticated user whose role is 'admin', distinct from fake_current_user."""
    return SimpleNamespace(
        id=uuid4(),
        email="admin@example.com",
        cognito_sub="cognito-sub-admin",
        role=SimpleNamespace(name="admin"),
    )


@pytest.fixture()
def fake_regular_user():
    """An authenticated user whose role is 'user' (non-admin)."""
    return SimpleNamespace(
        id=uuid4(),
        email="regular@example.com",
        cognito_sub="cognito-sub-regular",
        role=SimpleNamespace(name="user"),
    )


def test_admin_can_update_another_user_returns_200(
    app, client, fake_admin_user, fake_target_user
):
    """PATCH /api/v1/users/{other-user-id} by an admin returns 200 with updated profile."""
    # The target user's id differs from the admin's id — admin is updating someone else.
    updated_target = SimpleNamespace(
        id=fake_target_user.id,
        email=fake_target_user.email,
        first_name="AdminUpdated",
        last_name=fake_target_user.last_name,
        phone_number=fake_target_user.phone_number,
        avatar_url=fake_target_user.avatar_url,
        role=fake_target_user.role,
        created_at=fake_target_user.created_at,
        updated_at=fake_target_user.updated_at,
        deleted_at=fake_target_user.deleted_at,
        cognito_sub=fake_target_user.cognito_sub,
    )

    app.dependency_overrides[get_current_user] = lambda: fake_admin_user

    mock_user_service = AsyncMock()
    mock_user_service.update_user = AsyncMock(return_value=updated_target)

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.patch(
        f"/api/v1/users/{fake_target_user.id}",
        json={"first_name": "AdminUpdated"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "AdminUpdated"
    assert data["id"] == str(fake_target_user.id)


def test_admin_get_user_by_id_with_include_deleted_true_returns_200(
    app, client, fake_admin_user, fake_target_user
):
    """GET /api/v1/users/{id}?include_deleted=true called by an admin returns 200 and passes include_deleted=True to the service."""
    from datetime import datetime, timezone

    # Mark the target user as soft-deleted so we can verify a deleted record is returned.
    fake_target_user.deleted_at = datetime(2024, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

    app.dependency_overrides[get_current_user] = lambda: fake_admin_user

    mock_user_service = AsyncMock()
    mock_user_service.get_by_id = AsyncMock(return_value=fake_target_user)

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.get(f"/api/v1/users/{fake_target_user.id}?include_deleted=true")

    assert response.status_code == 200
    # Verify the service layer received include_deleted=True from the query param.
    mock_user_service.get_by_id.assert_awaited_once_with(
        fake_target_user.id,
        include_deleted=True,
        current_user=fake_admin_user,
    )


def test_non_admin_include_deleted_query_param_is_passed_through_to_service(
    app, client, fake_regular_user, fake_target_user
):
    """GET /api/v1/users/{id}?include_deleted=true by a non-admin passes the param to the service; downgrade enforcement is the service's responsibility."""
    app.dependency_overrides[get_current_user] = lambda: fake_regular_user

    mock_user_service = AsyncMock()
    mock_user_service.get_by_id = AsyncMock(return_value=fake_target_user)

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.get(f"/api/v1/users/{fake_target_user.id}?include_deleted=true")

    assert response.status_code == 200
    # The router passes include_deleted=True as supplied; the service decides
    # whether to honour it based on the current_user's role.
    mock_user_service.get_by_id.assert_awaited_once_with(
        fake_target_user.id,
        include_deleted=True,
        current_user=fake_regular_user,
    )


@pytest.mark.anyio
async def test_require_role_raises_403_for_wrong_role_and_returns_user_for_correct_role():
    """require_role inner checker raises HTTPException(403) for a non-matching role and returns the user when the role matches."""
    from app.core.dependencies import require_role

    non_admin_user = SimpleNamespace(
        id=uuid4(),
        email="plain@example.com",
        cognito_sub="cognito-sub-plain",
        role=SimpleNamespace(name="user"),
    )

    admin_user = SimpleNamespace(
        id=uuid4(),
        email="boss@example.com",
        cognito_sub="cognito-sub-boss",
        role=SimpleNamespace(name="admin"),
    )

    # Obtain the inner coroutine function produced by require_role("admin").
    role_checker = require_role("admin")

    # --- Wrong role: should raise 403 ---
    with pytest.raises(HTTPException) as exc_info:
        # Call the inner _role_checker directly, bypassing FastAPI's DI system.
        await role_checker(current_user=non_admin_user)
    assert exc_info.value.status_code == 403

    # --- Correct role: should return the user object unchanged ---
    result = await role_checker(current_user=admin_user)
    assert result is admin_user


# ---------------------------------------------------------------------------
# Slice 6 — DELETE /api/v1/users/{id} and soft-delete auth rejection
# ---------------------------------------------------------------------------


def test_admin_delete_user_returns_204(app, client, fake_admin_user, fake_target_user):
    """DELETE /api/v1/users/{id} by an admin returns 204 No Content on success."""
    app.dependency_overrides[get_current_user] = lambda: fake_admin_user

    mock_user_service = AsyncMock()
    mock_user_service.delete_user = AsyncMock(return_value=None)

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.delete(f"/api/v1/users/{fake_target_user.id}")

    assert response.status_code == 204
    # Confirm the service received the exact user id that was in the URL path.
    mock_user_service.delete_user.assert_awaited_once_with(fake_target_user.id)


def test_non_admin_delete_user_returns_403(
    app, client, fake_regular_user, fake_target_user
):
    """DELETE /api/v1/users/{id} by a non-admin is rejected by require_role with 403."""
    # Override get_current_user with a regular (non-admin) user so that
    # require_role("admin") resolves it and raises 403 due to role mismatch.
    app.dependency_overrides[get_current_user] = lambda: fake_regular_user

    response = client.delete(f"/api/v1/users/{fake_target_user.id}")

    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Insufficient permissions"
    assert body["errorCode"] == "FORBIDDEN"


def test_admin_delete_already_deleted_user_returns_404(
    app, client, fake_admin_user, fake_target_user
):
    """DELETE /api/v1/users/{id} for a soft-deleted user propagates the 404 raised by the service."""
    app.dependency_overrides[get_current_user] = lambda: fake_admin_user

    mock_user_service = AsyncMock()
    mock_user_service.delete_user = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="User not found")
    )

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.delete(f"/api/v1/users/{fake_target_user.id}")

    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "User not found"
    assert body["errorCode"] == "NOT_FOUND"


def test_deactivated_user_token_rejected_returns_401(app, client, fake_target_user):
    """Any authenticated endpoint returns 401 when get_current_user detects a deactivated account.

    The real get_current_user raises HTTPException(401) when the user record has
    deleted_at set (indicating a soft-deleted / deactivated account).  Overriding
    the dependency to reproduce that behaviour confirms the endpoint surfaces the
    error correctly through the FastAPI dependency chain.
    """

    # Simulate get_current_user raising the deactivated-account error that the
    # real implementation raises when deleted_at is not None.
    def deactivated_user():
        raise HTTPException(status_code=401, detail="User account has been deactivated")

    app.dependency_overrides[get_current_user] = deactivated_user

    # Use the GET /users/{id} endpoint as a representative authenticated route.
    response = client.get(f"/api/v1/users/{fake_target_user.id}")

    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "User account has been deactivated"
    assert body["errorCode"] == "UNAUTHORIZED"


def test_get_soft_deleted_user_without_include_deleted_returns_404(
    app, client, fake_admin_user, fake_target_user
):
    """GET /api/v1/users/{id} without include_deleted=true returns 404 for a soft-deleted user.

    After a user is soft-deleted, ordinary lookups (include_deleted=False, the
    default) must not expose the record.  The service enforces this and raises 404;
    the router must propagate it unchanged.
    """
    app.dependency_overrides[get_current_user] = lambda: fake_admin_user

    mock_user_service = AsyncMock()
    mock_user_service.get_by_id = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="User not found")
    )

    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    response = client.get(f"/api/v1/users/{fake_target_user.id}")

    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "User not found"
    assert body["errorCode"] == "NOT_FOUND"
