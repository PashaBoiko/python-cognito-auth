"""Service that orchestrates the full OAuth 2.0 authorization-code authentication flow.

Coordinates three layers:

1. ``CognitoService`` — exchanges the authorization code for Cognito tokens and
   resolves the caller's identity from the ``/oauth2/userInfo`` endpoint.
2. ``UserRepository`` — looks up or creates the user record and persists all
   token fields so the session can be revoked server-side.
3. JWT issuance — signs a short-lived application JWT with the ``JWT_SECRET``
   so that subsequent requests can be authenticated without hitting Cognito.

The ``AsyncSession`` is held directly rather than buried in a repository so
that the service can query supporting tables (e.g. ``roles``) without
introducing a full second repository class for a single look-up.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import jwt_settings
from app.models.role import Role
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.cognito_service import CognitoService

logger = logging.getLogger(__name__)

# Role name that is assigned to every newly registered user by default.
_DEFAULT_ROLE_NAME = "user"


class AuthService:
    """Orchestrates the end-to-end login flow for the application.

    Accepts the three collaborators via constructor injection so that each can
    be replaced with a test double in unit tests without patching module globals.

    Args:
        cognito_service: HTTP wrapper around the Cognito hosted-UI endpoints.
        user_repository: Data-access layer for the ``users`` table.
        session: Request-scoped async SQLAlchemy session used for role look-ups.
            The same session is shared with ``user_repository`` so all reads and
            writes participate in the same transaction.
    """

    def __init__(
        self,
        cognito_service: CognitoService,
        user_repository: UserRepository,
        session: AsyncSession,
    ) -> None:
        self._cognito = cognito_service
        self._repo = user_repository
        self._session = session

    async def authenticate(self, code: str) -> dict:
        """Run the full authorization-code exchange and return auth artefacts.

        Steps:
        1. Exchange the authorization code for Cognito tokens.
        2. Fetch the user's identity claims from the Cognito ``/userInfo`` endpoint.
        3. Look up the user in the database; create a new record if absent.
        4. Persist the Cognito OAuth tokens on the user record.
        5. Issue a signed application JWT.
        6. Persist the application token on the user record.

        Args:
            code: OAuth 2.0 authorization code received from the Cognito hosted UI.

        Returns:
            A dict with keys:

            - ``user`` — the populated ``User`` ORM instance (role eagerly loaded)
            - ``token`` — the signed application JWT string
            - ``expires_in`` — token lifetime expressed in seconds

        Raises:
            HTTPException: 401 when Cognito rejects the authorization code or
                the ``/userInfo`` request fails (propagated from ``CognitoService``).
            sqlalchemy.exc.NoResultFound: when the ``user`` role does not exist in
                the database — indicates a misconfigured seed.
        """
        # Step 1 — exchange the authorization code for Cognito tokens.
        tokens = await self._cognito.exchange_code_for_token(code)

        # Step 2 — resolve the caller's identity claims.
        user_info = await self._cognito.get_user_info(tokens["access_token"])

        # Step 3 — look up or provision the user record.
        user: User | None = await self._repo.get_by_email(user_info["email"])

        if user is None:
            user = await self._create_new_user(
                email=user_info["email"],
                cognito_sub=user_info["sub"],
            )
            logger.info("Provisioned new user for email=%s", user_info["email"])
        else:
            logger.debug("Found existing user id=%s for email=%s", user.id, user_info["email"])

        # Step 4 — persist the Cognito OAuth tokens.
        await self._repo.update_oauth_tokens(
            user,
            tokens["access_token"],
            tokens["refresh_token"],
            tokens["id_token"],
            tokens["expires_in"],
        )

        # Step 5 — issue a signed application JWT.
        app_token = self._issue_jwt(user)

        # Step 6 — persist the application token for server-side revocation.
        await self._repo.update_token(user, app_token)

        return {
            "user": user,
            "token": app_token,
            "expires_in": jwt_settings.JWT_EXPIRATION_HOURS * 3600,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _create_new_user(self, email: str, cognito_sub: str) -> User:
        """Look up the default role and insert a new user row.

        Args:
            email: Email address obtained from the Cognito ``/userInfo`` endpoint.
            cognito_sub: Cognito unique subject identifier for the user.

        Returns:
            The newly created ``User`` ORM instance (flushed but not yet committed).

        Raises:
            sqlalchemy.exc.NoResultFound: if the ``user`` role is missing from the DB.
        """
        result = await self._session.execute(
            select(Role).where(Role.name == _DEFAULT_ROLE_NAME)
        )
        # scalar_one() raises NoResultFound if the seed role is absent, which
        # is the correct behaviour — the application is misconfigured, not the caller.
        default_role = result.scalar_one()

        return await self._repo.create(
            email=email,
            cognito_sub=cognito_sub,
            role_id=default_role.id,
        )

    def _issue_jwt(self, user: User) -> str:
        """Sign and return a short-lived application JWT for the given user.

        The payload contains the minimum claims needed for request authentication:
        ``sub`` (user UUID as string) and ``email``.  The ``exp`` claim is set to
        ``now + JWT_EXPIRATION_HOURS`` so the token self-expires without server
        intervention.

        Args:
            user: The authenticated ``User`` ORM instance.

        Returns:
            A signed JWT string encoded with HS256.
        """
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "exp": datetime.now(timezone.utc)
            + timedelta(hours=jwt_settings.JWT_EXPIRATION_HOURS),
        }
        return jwt.encode(payload, jwt_settings.JWT_SECRET, algorithm="HS256")
