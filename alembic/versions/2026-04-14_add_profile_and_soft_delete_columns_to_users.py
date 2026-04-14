"""add profile and soft delete columns to users

Revision ID: d8c78cdbd3a4
Revises: a3f7c12e9d04
Create Date: 2026-04-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8c78cdbd3a4'
down_revision: Union[str, Sequence[str], None] = 'a3f7c12e9d04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user profile fields and soft-delete timestamp.

    - first_name, last_name: basic profile information
    - phone_number: E.164 format, max 16 characters
    - avatar_url: URL to the user's profile picture
    - deleted_at: soft-delete marker; NULL means the record is active
    """
    op.add_column('users', sa.Column('first_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('phone_number', sa.String(length=16), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Remove profile fields and soft-delete timestamp from users."""
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'phone_number')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
