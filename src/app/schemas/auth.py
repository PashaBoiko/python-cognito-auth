"""Pydantic schemas for the authentication API contract.

These models define the request payloads and response shapes for all routes
under the ``/auth`` prefix.  Keeping them separate from ORM models ensures
that the API surface is decoupled from the database schema — changes to either
do not automatically affect the other.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class AuthCodeRequest(BaseModel):
    """Payload sent by the client to initiate the OAuth 2.0 code exchange."""

    code: str


class UserResponse(BaseModel):
    """Public representation of a user returned by auth endpoints.

    ``from_attributes=True`` allows this model to be populated directly from
    a SQLAlchemy ORM instance, so callers can write
    ``UserResponse.model_validate(user_orm_obj)`` without manually mapping
    fields.

    The ``role`` field accepts either a plain ``str`` or a SQLAlchemy ``Role``
    ORM instance — the validator normalises both to a string by reading the
    ``.name`` attribute when the value is not already a string.  This avoids
    coupling the schema to the ORM type while still supporting convenient
    ``model_validate(user_orm_obj)`` call sites.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    cognito_sub: str
    role: str

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role_to_name(cls, value: Any) -> str:
        """Resolve a Role ORM object to its ``name`` string.

        When ``from_attributes=True`` is active and the ORM ``User.role``
        relationship is traversed, Pydantic passes the ``Role`` instance here.
        Returning ``value.name`` normalises it to a plain string without
        requiring callers to unpack the relationship manually.
        """
        if isinstance(value, str):
            return value
        # Duck-type: any object with a ``name`` attribute (e.g. Role ORM model)
        # is accepted so this validator does not introduce a hard import of the
        # ORM layer into the schema module.
        if hasattr(value, "name"):
            return str(value.name)
        raise ValueError(f"Cannot coerce value of type {type(value)!r} to a role name string")


class AuthResponse(BaseModel):
    """Full response returned after a successful authentication."""

    user: UserResponse
    token: str
    expires_in: int


class MessageResponse(BaseModel):
    """Generic response for operations that return only a human-readable message."""

    message: str
