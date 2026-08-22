"""add goal_period_history

Revision ID: d4e6b8a1f930
Revises: c1a9f4d7e528
Create Date: 2026-08-22 20:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e6b8a1f930'
down_revision: Union[str, None] = 'c1a9f4d7e528'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'goal_period_history',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('goal_id', sa.BigInteger(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('target', sa.Integer(), nullable=False),
        sa.Column('current', sa.Integer(), nullable=False),
        sa.Column('achieved', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_goal_period_history_goal_id'), 'goal_period_history', ['goal_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_goal_period_history_goal_id'), table_name='goal_period_history')
    op.drop_table('goal_period_history')
