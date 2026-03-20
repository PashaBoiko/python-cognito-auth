"""FastAPI dependency providers for shared request-scoped resources.

Each function in this module is designed to be used with FastAPI's
``Depends()`` mechanism.  Dependency injection ensures that resources such as
database sessions are properly initialised before a route handler runs and
cleaned up after the response is sent, even when an exception is raised.
"""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import jwt_settings
from app.core.database import async_session_maker
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.cognito_service import CognitoService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional ``AsyncSession`` for the duration of a request.

    The session is obtained from ``async_session_maker`` via an async context
    manager, which guarantees that the underlying connection is returned to the
    pool once the request completes — regardless of whether it succeeded or
    raised an exception.

    Usage in a route handler::

        from fastapi import Depends
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.core.dependencies import get_db_session

        @router.get("/example")
        async def example_route(
            session: AsyncSession = Depends(get_db_session),
        ) -> ...:
            ...
    """
    async with async_session_maker() as session:
        yield session


async def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    """Construct a ``UserRepository`` bound to the current request session.

    The same ``AsyncSession`` yielded by ``get_db_session`` is reused here
    so that repository operations and any direct session queries inside a
    service participate in the same transaction.

    Args:
        session: Request-scoped async session injected by FastAPI.

    Returns:
        A ``UserRepository`` instance ready for use within the request lifecycle.
    """
    return UserRepository(session)


def get_cognito_service() -> CognitoService:
    """Construct a stateless ``CognitoService`` instance.

    ``CognitoService`` holds no mutable state between calls — each method
    opens its own ``httpx.AsyncClient`` — so a new instance per request is
    safe and avoids shared-state concurrency hazards.

    Returns:
        A fresh ``CognitoService`` instance.
    """
    return CognitoService()


async def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    cognito_service: CognitoService = Depends(get_cognito_service),
    user_repository: UserRepository = Depends(get_user_repository),
) -> AuthService:
    """Construct an ``AuthService`` wired to all its collaborators.

    The ``session`` is passed directly to ``AuthService`` (in addition to
    being embedded in ``user_repository``) so the service can perform
    supplementary queries — such as looking up the default role — without
    introducing a second repository class.

    FastAPI deduplicates ``Depends(get_db_session)`` across the dependency
    graph, so both ``session`` and ``user_repository`` share the same
    ``AsyncSession`` instance within a single request.

    Args:
        session: Request-scoped async session.
        cognito_service: Stateless Cognito HTTP wrapper.
        user_repository: Data-access layer for the ``users`` table.

    Returns:
        A fully wired ``AuthService`` ready to orchestrate the auth flow.
    """
    return AuthService(cognito_service, user_repository, session)


async def get_current_user(
    request: Request,
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    """Authenticate the incoming request by validating its Bearer JWT.

    Performs a two-stage check:

    1. **Structural/cryptographic** — the token must be a well-formed HS256 JWT
       signed with ``JWT_SECRET`` and must contain a ``sub`` claim that parses
       as a UUID.
    2. **Revocation** — the ``(id, token)`` pair must still exist in the
       database; ``clear_token`` sets ``token`` to ``NULL`` on logout, so any
       token issued before the last logout will fail this check.

    This dependency can be added to any route that requires an authenticated
    user::

        from app.core.dependencies import get_current_user

        @router.get("/protected")
        async def protected_route(
            current_user: User = Depends(get_current_user),
        ) -> ...:
            ...

    Args:
        request: The incoming FastAPI request, used to read the
            ``Authorization`` header.
        user_repository: Data-access layer injected by FastAPI; shares the
            request-scoped ``AsyncSession`` with other dependencies.

    Returns:
        The authenticated ``User`` ORM instance.

    Raises:
        HTTPException: 401 when the header is absent, the token is
            malformed/expired, the payload is missing ``sub``, or the token
            has been revoked in the database.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header",
        )

    token = auth_header.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(token, jwt_settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        # ``sub`` was present but not a valid UUID — treat as a malformed token.
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await user_repository.get_by_id_and_token(user_id, token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Token has been revoked or user not found",
        )

    return user
