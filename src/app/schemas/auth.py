from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class AuthCodeRequest(BaseModel):
    code: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    cognito_sub: str
    role: str

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role_to_name(cls, value: Any) -> str:

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


class AuthResponse(BaseModel):
    user: UserResponse
    token: str
    expires_in: int


class MessageResponse(BaseModel):
    message: str
