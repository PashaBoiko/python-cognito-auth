"""drop token column from users

Revision ID: a3f7c12e9d04
Revises: 10edf196c4b5
Create Date: 2026-03-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a3f7c12e9d04'
down_revision: Union[str, Sequence[str], None] = '10edf196c4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the application session token column.

    Token storage has been moved to Redis via TokenService, so the
    per-row ``token`` column in the ``users`` table is no longer needed.
    """
    op.drop_column('users', 'token')


def downgrade() -> None:
    """Restore the application session token column."""
    op.add_column('users', sa.Column('token', sa.Text(), nullable=True))
