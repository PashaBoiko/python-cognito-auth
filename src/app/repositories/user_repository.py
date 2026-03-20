from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:

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
        user.oauth_access_token = access_token
        user.oauth_refresh_token = refresh_token
        user.oauth_id_token = id_token
        user.oauth_expires_at = datetime.now(tz=timezone.utc) + timedelta(
            seconds=expires_in
        )
        await self._session.commit()
        await self._session.refresh(user)

    async def update_token(self, user: User, token: str) -> None:
        user.token = token
        await self._session.commit()
        await self._session.refresh(user)

    async def get_by_id_and_token(
        self, user_id: uuid.UUID, token: str
    ) -> User | None:
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.token == token)
        )
        return result.scalars().first()

    async def clear_token(self, user: User) -> None:
        user.token = None
        await self._session.commit()
        await self._session.refresh(user)
