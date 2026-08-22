"""add user_settings.hidden_goal_ids and goal_order

Revision ID: c1a9f4d7e528
Revises: b8d4e2f6a013
Create Date: 2026-08-22 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c1a9f4d7e528'
down_revision: Union[str, None] = 'b8d4e2f6a013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_settings',
        sa.Column('hidden_goal_ids', postgresql.ARRAY(sa.BigInteger()), nullable=False, server_default='{}'),
    )
    op.add_column(
        'user_settings',
        sa.Column('goal_order', postgresql.ARRAY(sa.BigInteger()), nullable=False, server_default='{}'),
    )
    op.alter_column('user_settings', 'hidden_goal_ids', server_default=None)
    op.alter_column('user_settings', 'goal_order', server_default=None)


def downgrade() -> None:
    op.drop_column('user_settings', 'goal_order')
    op.drop_column('user_settings', 'hidden_goal_ids')
