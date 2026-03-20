from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

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
    def __init__(
        self,
        cognito_service: CognitoService,
        user_repository: UserRepository,
        session: AsyncSession,
    ) -> None:
        self._cognito = cognito_service
        self._repo = user_repository
        self._session = session

    async def authenticate(self, code: str) -> dict[str, object]:

        tokens = await self._cognito.exchange_code_for_token(code)

        user_info = await self._cognito.get_user_info(tokens["access_token"])

        user: User | None = await self._repo.get_by_email(user_info["email"])

        if user is None:
            user = await self._create_new_user(
                email=user_info["email"],
                cognito_sub=user_info["sub"],
            )
            logger.info("Provisioned new user for email=%s", user_info["email"])
        else:
            logger.debug(
                "Found existing user id=%s for email=%s",
                user.id,
                user_info["email"],
            )

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
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "exp": datetime.now(UTC)
            + timedelta(hours=jwt_settings.JWT_EXPIRATION_HOURS),
        }
        token: str = jwt.encode(payload, jwt_settings.JWT_SECRET, algorithm="HS256")
        return token
