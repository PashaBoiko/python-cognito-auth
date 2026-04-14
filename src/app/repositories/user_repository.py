from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(
        self,
        email: str,
        include_deleted: bool = False,
    ) -> User | None:
        statement = select(User).where(func.lower(User.email) == email.lower())
        if not include_deleted:
            statement = statement.where(User.deleted_at.is_(None))
        result = await self._session.execute(statement)
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
        user.oauth_expires_at = datetime.now(tz=UTC) + timedelta(seconds=expires_in)
        await self._session.commit()
        await self._session.refresh(user)

    async def get_by_id(
        self,
        user_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> User | None:
        statement = select(User).where(User.id == user_id)
        if not include_deleted:
            statement = statement.where(User.deleted_at.is_(None))
        result = await self._session.execute(statement)
        return result.scalars().first()

    async def list_users(
        self,
        offset: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[User], int]:
        """Return a paginated list of users and the total count.

        Args:
            offset: Number of rows to skip before returning results.
            limit: Maximum number of users to return.
            include_deleted: When False, rows with a non-null deleted_at
                are excluded from both the result list and the total count.

        Returns:
            A tuple of (users, total_count).
        """
        base_statement = select(User)
        if not include_deleted:
            base_statement = base_statement.where(User.deleted_at.is_(None))

        # Total count (uses the same filter so soft-deleted rows stay excluded)
        count_statement = select(func.count()).select_from(base_statement.subquery())
        count_result = await self._session.execute(count_statement)
        total_count: int = count_result.scalar_one()

        # Paginated user rows
        paginated_statement = base_statement.offset(offset).limit(limit)
        users_result = await self._session.execute(paginated_statement)
        users: list[User] = list(users_result.scalars().all())

        return users, total_count

    async def soft_delete(self, user: User) -> User:
        user.deleted_at = datetime.now(tz=UTC)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update(self, user: User, **fields: object) -> User:
        for key, value in fields.items():
            setattr(user, key, value)
        await self._session.flush()
        await self._session.refresh(user)
        return user
