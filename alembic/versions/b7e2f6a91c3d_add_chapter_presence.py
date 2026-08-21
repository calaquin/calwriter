"""add chapter presence

Revision ID: b7e2f6a91c3d
Revises: f3c8d1a4e7b2
Create Date: 2026-08-21 21:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e2f6a91c3d'
down_revision: Union[str, None] = 'f3c8d1a4e7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chapter_presence',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('chapter_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chapter_id', 'user_id', name='uq_chapter_presence_chapter_user'),
    )
    op.create_index('ix_chapter_presence_chapter_id', 'chapter_presence', ['chapter_id'])


def downgrade() -> None:
    op.drop_index('ix_chapter_presence_chapter_id', table_name='chapter_presence')
    op.drop_table('chapter_presence')
