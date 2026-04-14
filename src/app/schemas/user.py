from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

# E.164 international phone number format:
# starts with '+', followed by 1-9, then 1-14 additional digits.
_E164_PATTERN: re.Pattern[str] = re.compile(r"^\+[1-9]\d{1,14}$")


class UserProfileResponse(BaseModel):
    """Public-facing user profile representation.

    Deliberately excludes ``cognito_sub`` because it is an internal
    implementation detail that should never leak to API consumers.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    phone_number: str | None
    avatar_url: str | None
    role: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role_to_name(cls, value: Any) -> str:
        """Coerce a Role ORM object to its name string.

        Accepts a plain string (pass-through) or any object with a ``name``
        attribute (e.g. the ``Role`` SQLAlchemy model) so the schema module
        stays decoupled from the ORM layer.
        """
        if isinstance(value, str):
            return value
        # Duck-type: any object with a ``name`` attribute (e.g. Role ORM model)
        # is accepted so this validator does not introduce a hard import of the
        # ORM layer into the schema module.
        if hasattr(value, "name"):
            return str(value.name)
        raise ValueError(
            f"Cannot coerce value of type {type(value)!r} to a role name string"
        )


class PaginatedUserResponse(BaseModel):
    """Paginated list of user profiles.

    Manually constructed by the service layer -- no ORM mapping needed.
    """

    items: list[UserProfileResponse]
    total: int
    offset: int
    limit: int


class UserUpdateRequest(BaseModel):
    """Partial-update request for a user profile.

    All fields default to ``None`` -- only the fields that are explicitly
    provided in the request body will be updated.  ``email`` and ``role_id``
    are accepted here so the *service layer* can detect them and reject the
    update for non-admin callers.
    """

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone_number: str | None = None
    avatar_url: str | None = None
    email: str | None = None
    role_id: uuid.UUID | None = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number_e164(cls, value: str | None) -> str | None:
        """Ensure ``phone_number`` conforms to E.164 format when provided."""
        if value is None:
            return value
        if not _E164_PATTERN.match(value):
            raise ValueError("phone_number must be in E.164 format, e.g. +14155552671")
        return value

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url_is_http(cls, value: str | None) -> str | None:
        """Ensure ``avatar_url`` is a valid HTTP or HTTPS URL when provided.

        Uses Pydantic's ``AnyHttpUrl`` for validation, then converts back to
        ``str`` so downstream code does not need to handle the ``AnyHttpUrl``
        type.
        """
        if value is None:
            return value
        # AnyHttpUrl validates the string and raises ValueError on failure.
        AnyHttpUrl(value)
        return value
