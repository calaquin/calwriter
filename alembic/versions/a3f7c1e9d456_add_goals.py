"""add chapters.completed_at and goals table

Revision ID: a3f7c1e9d456
Revises: e8a4c6f19d02
Create Date: 2026-08-22 15:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f7c1e9d456'
down_revision: Union[str, None] = 'e8a4c6f19d02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chapters', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'goals',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('folder_id', sa.BigInteger(), nullable=True),
        sa.Column('chapter_id', sa.BigInteger(), nullable=True),
        sa.Column('goal_type', sa.Enum('words', 'chapters', name='goal_type'), nullable=False),
        sa.Column('target', sa.Integer(), nullable=False),
        sa.Column('cadence', sa.Enum('daily', 'weekly', 'monthly', name='goal_cadence'), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('baseline_word_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            '(folder_id IS NOT NULL)::int + (chapter_id IS NOT NULL)::int = 1',
            name='chk_goals_one_target',
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['folder_id'], ['folders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_goals_user_id'), 'goals', ['user_id'])
    op.create_index(op.f('ix_goals_folder_id'), 'goals', ['folder_id'])
    op.create_index(op.f('ix_goals_chapter_id'), 'goals', ['chapter_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_goals_chapter_id'), table_name='goals')
    op.drop_index(op.f('ix_goals_folder_id'), table_name='goals')
    op.drop_index(op.f('ix_goals_user_id'), table_name='goals')
    op.drop_table('goals')
    sa.Enum(name='goal_cadence').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='goal_type').drop(op.get_bind(), checkfirst=True)

    op.drop_column('chapters', 'completed_at')
