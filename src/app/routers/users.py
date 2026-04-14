from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, get_user_service, require_role
from app.models.user import User
from app.schemas.user import (
    PaginatedUserResponse,
    UserProfileResponse,
    UserUpdateRequest,
)
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Users"])


@router.get(
    "/users",
    response_model=PaginatedUserResponse,
    summary="List users",
    description=(
        "Returns a paginated list of active users. "
        "Requires a valid Bearer token in the ``Authorization`` header. "
        "Use the ``offset`` and ``limit`` query parameters to control "
        "pagination (``limit`` is capped at 100)."
    ),
)
async def list_users(
    offset: int = 0,
    limit: int = Query(default=20, le=100),
    include_deleted: bool = False,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> PaginatedUserResponse:
    users, total_count = await user_service.list_users(
        offset=offset,
        limit=limit,
        include_deleted=include_deleted,
        current_user=current_user,
    )
    return PaginatedUserResponse(
        items=[UserProfileResponse.model_validate(u) for u in users],
        total=total_count,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/users/{id}",
    response_model=UserProfileResponse,
    summary="Get a user by ID",
    description=(
        "Retrieves the public profile of a user by their unique identifier. "
        "Requires a valid Bearer token in the ``Authorization`` header. "
        "Returns HTTP 404 when the requested user does not exist or has been "
        "soft-deleted."
    ),
)
async def get_user_by_id(
    id: uuid.UUID,
    include_deleted: bool = False,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    user = await user_service.get_by_id(
        id,
        include_deleted=include_deleted,
        current_user=current_user,
    )
    return UserProfileResponse.model_validate(user)


@router.get(
    "/users/by-email/{email}",
    response_model=UserProfileResponse,
    summary="Get a user by email",
    description=(
        "Retrieves the public profile of a user by their email address. "
        "Requires a valid Bearer token in the ``Authorization`` header. "
        "Returns HTTP 404 when a user with the given email does not exist "
        "or has been soft-deleted."
    ),
)
async def get_user_by_email(
    email: str,
    include_deleted: bool = False,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    user = await user_service.get_by_email(
        email,
        include_deleted=include_deleted,
        current_user=current_user,
    )
    return UserProfileResponse.model_validate(user)


@router.patch(
    "/users/{id}",
    response_model=UserProfileResponse,
    summary="Update a user profile",
    description=(
        "Partially updates the authenticated user's own profile. "
        "Only the fields provided in the request body are updated. "
        "Non-admin users may update ``first_name``, ``last_name``, "
        "``phone_number``, and ``avatar_url``. Attempting to modify "
        "``email`` or ``role_id`` returns HTTP 403. Updating another "
        "user's profile also returns HTTP 403."
    ),
)
async def update_user(
    id: uuid.UUID,
    update_data: UserUpdateRequest,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    user = await user_service.update_user(id, update_data, current_user)
    return UserProfileResponse.model_validate(user)


@router.delete(
    "/users/{id}",
    status_code=204,
    summary="Delete a user (soft delete)",
    description=(
        "Soft-deletes the user identified by the given UUID and disables "
        "their Cognito account. Only users with the ``admin`` role are "
        "permitted to perform this operation. Returns HTTP 204 on success "
        "and HTTP 404 when the user does not exist."
    ),
)
async def delete_user(
    id: uuid.UUID,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(require_role("admin")),
) -> None:
    await user_service.delete_user(id)
