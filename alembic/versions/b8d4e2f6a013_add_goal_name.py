"""add goals.name (optional user-chosen label)

Revision ID: b8d4e2f6a013
Revises: a3f7c1e9d456
Create Date: 2026-08-22 19:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8d4e2f6a013'
down_revision: Union[str, None] = 'a3f7c1e9d456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('goals', sa.Column('name', sa.String(length=255), nullable=False, server_default=''))
    op.alter_column('goals', 'name', server_default=None)


def downgrade() -> None:
    op.drop_column('goals', 'name')
