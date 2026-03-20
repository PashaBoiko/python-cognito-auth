from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.core.dependencies import get_auth_service, get_current_user, get_user_repository
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthCodeRequest, AuthResponse, MessageResponse, UserResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.post(
    "/auth",
    response_model=AuthResponse,
    summary="Exchange authorization code for application token",
    description=(
        "Accepts an OAuth 2.0 authorization code from the Cognito hosted UI, "
        "exchanges it for Cognito tokens, looks up or provisions the user in the "
        "application database, and returns a signed application JWT. "
        "Returns HTTP 401 when the code is invalid or expired."
    ),
)
async def token_exchange(
    body: AuthCodeRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:

    result = await auth_service.authenticate(body.code)

    return AuthResponse(
        user=UserResponse.model_validate(result["user"]),
        token=result["token"],
        expires_in=result["expires_in"],
    )


@router.post(
    "/auth/validate",
    response_model=UserResponse,
    summary="Validate an application JWT and return the authenticated user",
    description=(
        "Verifies the Bearer token supplied in the ``Authorization`` header "
        "against both the JWT signature and the server-side revocation record. "
        "Returns the authenticated user's public profile on success, or HTTP 401 "
        "when the token is absent, malformed, expired, or revoked."
    ),
)
async def validate_token(
    current_user: User = Depends(get_current_user),
) -> UserResponse:

    return UserResponse.model_validate(current_user)


@router.post(
    "/auth/logout",
    response_model=MessageResponse,
    summary="Revoke the current application JWT",
    description=(
        "Clears the server-side token record for the authenticated user, "
        "immediately invalidating the supplied Bearer token.  Subsequent "
        "requests that present the same token will receive HTTP 401."
    ),
)
async def logout(
    current_user: User = Depends(get_current_user),
    user_repository: UserRepository = Depends(get_user_repository),
) -> MessageResponse:

    await user_repository.clear_token(current_user)
    return MessageResponse(message="Logged out successfully")
