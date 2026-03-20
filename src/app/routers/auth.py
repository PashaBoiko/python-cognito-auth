"""Authentication router — OAuth 2.0 authorization-code exchange and token endpoints.

Exposes three routes:

- ``POST /auth`` — exchange an OAuth 2.0 authorization code for an application JWT.
- ``POST /auth/validate`` — verify a Bearer token and return the authenticated user.
- ``POST /auth/logout`` — revoke the current Bearer token server-side.

All heavy lifting is delegated to service and repository collaborators; this
module owns only the HTTP surface (request parsing, response shaping, and
status codes).
"""

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
    """Handle the POST /auth request.

    Delegates to ``AuthService.authenticate`` which performs the full
    Cognito → DB → JWT flow.  The resulting ``User`` ORM instance is
    validated into a ``UserResponse`` by Pydantic using ``from_attributes``
    mode; the ``role`` field is resolved from the eagerly loaded relationship.

    Args:
        body: Request body containing the OAuth 2.0 authorization code.
        auth_service: Injected service that orchestrates the auth flow.

    Returns:
        ``AuthResponse`` containing the user profile, application JWT, and
        token lifetime in seconds.

    Raises:
        HTTPException: 401 when ``AuthService`` propagates a Cognito rejection.
    """
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
    """Return the authenticated user's public profile.

    The ``get_current_user`` dependency performs all token verification before
    this handler runs — it either resolves to a ``User`` instance or raises
    HTTP 401, so no additional checks are needed here.

    Args:
        current_user: Authenticated ``User`` ORM instance injected by
            ``get_current_user``.

    Returns:
        ``UserResponse`` populated from the ORM instance via ``from_attributes``
        mode.
    """
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
    """Revoke the authenticated user's current application token.

    ``get_current_user`` guarantees the token is valid before this handler
    runs.  ``clear_token`` sets ``User.token`` to ``NULL`` in the database,
    which causes all subsequent ``get_by_id_and_token`` lookups for this token
    to return ``None``.

    Args:
        current_user: Authenticated ``User`` ORM instance injected by
            ``get_current_user``.
        user_repository: Data-access layer used to perform the revocation
            write; shares the request-scoped session via FastAPI DI.

    Returns:
        ``MessageResponse`` confirming successful logout.
    """
    await user_repository.clear_token(current_user)
    return MessageResponse(message="Logged out successfully")
