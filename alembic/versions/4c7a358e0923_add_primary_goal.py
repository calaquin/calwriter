"""add primary goal

Revision ID: 4c7a358e0923
Revises: 642834d96895
Create Date: 2026-08-23 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '4c7a358e0923'
down_revision: Union[str, None] = '642834d96895'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_settings', sa.Column('primary_goal_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'user_settings_primary_goal_id_fkey', 'user_settings', 'goals', ['primary_goal_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('user_settings_primary_goal_id_fkey', 'user_settings', type_='foreignkey')
    op.drop_column('user_settings', 'primary_goal_id')
