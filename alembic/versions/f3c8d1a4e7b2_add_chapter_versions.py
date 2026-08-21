"""add chapter versions

Revision ID: f3c8d1a4e7b2
Revises: a1e7c3f92b6d
Create Date: 2026-08-21 20:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3c8d1a4e7b2'
down_revision: Union[str, None] = 'a1e7c3f92b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chapter_versions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('chapter_id', sa.BigInteger(), nullable=False),
        sa.Column('content_html', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chapter_versions_chapter_id', 'chapter_versions', ['chapter_id'])
    op.create_index('ix_chapter_versions_created_at', 'chapter_versions', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_chapter_versions_created_at', table_name='chapter_versions')
    op.drop_index('ix_chapter_versions_chapter_id', table_name='chapter_versions')
    op.drop_table('chapter_versions')
