from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserUpdateRequest
from app.services.cognito_service import CognitoService

logger = logging.getLogger(__name__)


class UserService:
    def __init__(
        self,
        user_repository: UserRepository,
        session: AsyncSession,
        cognito_service: CognitoService,
    ) -> None:
        self._repo = user_repository
        self._session = session
        self._cognito = cognito_service

    @staticmethod
    def _is_admin(user: User | None) -> bool:
        """Return ``True`` when the given user has the admin role."""
        if user is None:
            return False
        return user.role is not None and user.role.name == "admin"

    async def get_by_id(
        self,
        user_id: uuid.UUID,
        include_deleted: bool = False,
        current_user: User | None = None,
    ) -> User:
        """Fetch a single user by primary key.

        Delegates to ``UserRepository.get_by_id`` and raises a 404 error
        when the requested user does not exist (or has been soft-deleted
        and ``include_deleted`` is ``False``).

        When ``include_deleted`` is ``True``, only admin users are
        permitted to see soft-deleted records.  Non-admin callers have
        the flag silently reset to ``False``.
        """
        if include_deleted and not self._is_admin(current_user):
            include_deleted = False

        user: User | None = await self._repo.get_by_id(
            user_id, include_deleted=include_deleted
        )

        if user is None:
            logger.debug("User not found for id=%s", user_id)
            raise HTTPException(status_code=404, detail="User not found")

        return user

    async def list_users(
        self,
        offset: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
        current_user: User | None = None,
    ) -> tuple[list[User], int]:
        """Return a paginated list of users.

        Delegates to ``UserRepository.list_users``.  Returns a tuple of
        ``(users, total_count)`` -- no 404 logic is needed for list
        operations since an empty list is a valid result.

        When ``include_deleted`` is ``True``, only admin users are
        permitted to see soft-deleted records.  Non-admin callers have
        the flag silently reset to ``False``.
        """
        if include_deleted and not self._is_admin(current_user):
            include_deleted = False

        users, total = await self._repo.list_users(
            offset=offset,
            limit=limit,
            include_deleted=include_deleted,
        )
        return users, total

    async def update_user(
        self,
        user_id: uuid.UUID,
        update_data: UserUpdateRequest,
        current_user: User,
    ) -> User:
        """Update a user's profile.

        Admin users (``current_user.role.name == "admin"``) may update
        any user's profile and are allowed to change ``role_id``.

        Non-admin users can only update their own profile and are
        restricted to ``first_name``, ``last_name``, ``phone_number``,
        and ``avatar_url``.  Attempting to update another user's profile
        or to modify ``email`` / ``role_id`` results in a 403 error.

        Email changes are always forbidden regardless of role because
        they require a separate Cognito flow.
        """
        is_admin: bool = self._is_admin(current_user)

        # Non-admin users may only update their own profile
        if not is_admin and current_user.id != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only update your own profile",
            )

        # Detect forbidden fields before touching the database.
        # Email is always forbidden; role_id is forbidden for non-admins only.
        forbidden_fields: list[str] = []
        if update_data.email is not None:
            forbidden_fields.append("email")
        if update_data.role_id is not None and not is_admin:
            forbidden_fields.append("role")

        if forbidden_fields:
            raise HTTPException(
                status_code=403,
                detail=(
                    "You are not allowed to update the following fields: "
                    + ", ".join(forbidden_fields)
                ),
            )

        # Raises 404 when the user does not exist or is soft-deleted
        user: User = await self.get_by_id(user_id)

        fields: dict[str, object] = update_data.model_dump(exclude_unset=True)
        # Always strip email from the changeset (guarded above, but belt-and-suspenders)
        fields.pop("email", None)
        # Strip role_id for non-admins (guarded above, but keep the safety net)
        if not is_admin:
            fields.pop("role_id", None)

        if fields:
            await self._repo.update(user, **fields)

        await self._session.commit()
        return user

    async def get_by_email(
        self,
        email: str,
        include_deleted: bool = False,
        current_user: User | None = None,
    ) -> User:
        """Fetch a single user by email address.

        Delegates to ``UserRepository.get_by_email`` and raises a 404 error
        when the requested user does not exist (or has been soft-deleted
        and ``include_deleted`` is ``False``).

        When ``include_deleted`` is ``True``, only admin users are
        permitted to see soft-deleted records.  Non-admin callers have
        the flag silently reset to ``False``.
        """
        if include_deleted and not self._is_admin(current_user):
            include_deleted = False

        user: User | None = await self._repo.get_by_email(
            email, include_deleted=include_deleted
        )

        if user is None:
            logger.debug("User not found for email=%s", email)
            raise HTTPException(status_code=404, detail="User not found")

        return user

    async def delete_user(self, user_id: uuid.UUID) -> None:
        """Soft-delete a user and disable their Cognito account.

        Fetches the user by ``user_id`` (raises 404 if not found),
        marks the record as deleted via ``soft_delete``, disables
        the corresponding Cognito account, and commits the transaction.

        Authorization (admin-only) is enforced at the router level
        via ``require_role("admin")``.
        """
        user: User | None = await self._repo.get_by_id(user_id)
        if user is None:
            logger.debug("User not found for deletion, id=%s", user_id)
            raise HTTPException(status_code=404, detail="User not found")

        await self._repo.soft_delete(user)
        await self._cognito.admin_disable_user(user.cognito_sub)
        await self._session.commit()
