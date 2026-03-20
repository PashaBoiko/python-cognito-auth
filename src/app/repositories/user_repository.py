"""Repository for User database operations.

Encapsulates all SQL queries and mutations for the ``users`` table so that
higher-level service code never constructs raw queries directly.  All methods
are async and operate on the ``AsyncSession`` that is provided at construction
time, keeping the repository compatible with FastAPI's dependency injection
model.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Data-access layer for the ``users`` table.

    Accepts an ``AsyncSession`` at construction so that the same session (and
    therefore the same transaction) is shared across multiple repository calls
    within a single request.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        """Return the user with the given email address, or ``None``.

        Uses a parameterised ``WHERE`` clause to prevent SQL injection.
        """
        result = await self._session.execute(
            select(User).where(User.email == email)
        )
        return result.scalars().first()

    async def create(
        self,
        email: str,
        cognito_sub: str,
        role_id: uuid.UUID,
    ) -> User:
        """Insert a new user row and return the fully populated ``User`` object.

        ``flush`` sends the INSERT to the database within the current
        transaction without committing, which lets ``refresh`` load any
        server-generated values (e.g. ``id``, ``created_at``) back into the
        ORM instance before the transaction is finalised.
        """
        user = User(email=email, cognito_sub=cognito_sub, role_id=role_id)
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update_oauth_tokens(
        self,
        user: User,
        access_token: str,
        refresh_token: str,
        id_token: str,
        expires_in: int,
    ) -> None:
        """Persist the four Cognito OAuth token fields on the given user.

        ``oauth_expires_at`` is calculated as *now (UTC) + expires_in seconds*
        so the application can check token validity without decoding the JWT.
        """
        user.oauth_access_token = access_token
        user.oauth_refresh_token = refresh_token
        user.oauth_id_token = id_token
        user.oauth_expires_at = datetime.now(tz=timezone.utc) + timedelta(
            seconds=expires_in
        )
        await self._session.commit()
        await self._session.refresh(user)

    async def update_token(self, user: User, token: str) -> None:
        """Set the opaque application session token and persist it."""
        user.token = token
        await self._session.commit()
        await self._session.refresh(user)

    async def get_by_id_and_token(
        self, user_id: uuid.UUID, token: str
    ) -> User | None:
        """Return the user only when both ``id`` and ``token`` match.

        Used by the authentication guard to validate that the opaque session
        token presented in a request belongs to the claimed user.  Both
        conditions must hold simultaneously to prevent token substitution
        attacks.
        """
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.token == token)
        )
        return result.scalars().first()

    async def clear_token(self, user: User) -> None:
        """Revoke the opaque session token by setting it to ``None``."""
        user.token = None
        await self._session.commit()
        await self._session.refresh(user)
