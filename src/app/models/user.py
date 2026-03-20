from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.role import Role


class User(Base):

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        "id",
        type_=UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    cognito_sub: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        # Explicit FK name is not required here because the MetaData naming
        # convention on Base applies the ``%(table_name)s_%(column_0_name)s_fkey``
        # template automatically.
        UUID(as_uuid=True),
        ForeignKey("roles.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        # onupdate fires on SQLAlchemy-driven UPDATEs; the server_default
        # handles the initial value so no application-side logic is needed.
        onupdate=func.now(),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Application token
    # ------------------------------------------------------------------

    # Opaque session token issued by this service after a successful OAuth
    # exchange.  Stored so the service can revoke it server-side.
    token: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # ------------------------------------------------------------------
    # OAuth 2.0 tokens received from Cognito
    # ------------------------------------------------------------------

    # Raw access token from Cognito — kept so downstream calls to
    # Cognito-protected APIs can be made on behalf of the user.
    oauth_access_token: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    # Refresh token used to obtain a new access token without re-authenticating.
    oauth_refresh_token: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    # ID token (JWT) that carries the user's identity claims from Cognito.
    oauth_id_token: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    # UTC timestamp at which the Cognito access token expires; used to
    # trigger a refresh before making upstream calls.
    oauth_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    role: Mapped[Role] = relationship(
        "Role",
        back_populates="users",
        # selectin loading is preferred in async contexts: it avoids implicit
        # lazy I/O that would raise MissingGreenlet under asyncpg.
        lazy="selectin",
    )
