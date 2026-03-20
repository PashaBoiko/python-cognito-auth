from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        # Use the native PostgreSQL UUID type; as_uuid=True returns Python UUID objects.
        # gen_random_uuid() is a PostgreSQL built-in that avoids application-side
        # UUID generation and removes a round-trip for INSERT … RETURNING id.
        "id",
        type_=UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        # func.now() delegates timestamp generation to PostgreSQL, ensuring
        # consistent timezone-aware values regardless of the application server.
        server_default=func.now(),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    users: Mapped[list[User]] = relationship(
        "User",
        back_populates="role",
    )
