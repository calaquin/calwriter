"""recursive chapters + hierarchy safety

Revision ID: f4a2d9c6b731
Revises: e1b6c3a8f204
Create Date: 2026-08-24 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f4a2d9c6b731'
down_revision: Union[str, None] = 'e1b6c3a8f204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('chapters', 'folder_id', nullable=True)
    op.add_column(
        'chapters',
        sa.Column('parent_chapter_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'chapters_parent_chapter_id_fkey', 'chapters', 'chapters',
        ['parent_chapter_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_index('ix_chapters_parent_chapter_id', 'chapters', ['parent_chapter_id'])
    # Trivially valid immediately: every existing row already has
    # folder_id IS NOT NULL and parent_chapter_id IS NULL.
    op.create_check_constraint(
        'chk_chapters_one_parent', 'chapters',
        '(folder_id IS NOT NULL)::int + (parent_chapter_id IS NOT NULL)::int = 1',
    )
    op.create_unique_constraint(
        'uq_chapters_parent_chapter_name', 'chapters', ['parent_chapter_id', 'name'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_chapters_parent_chapter_name', 'chapters', type_='unique')
    op.drop_constraint('chk_chapters_one_parent', 'chapters', type_='check')
    op.drop_index('ix_chapters_parent_chapter_id', table_name='chapters')
    op.drop_constraint('chapters_parent_chapter_id_fkey', 'chapters', type_='foreignkey')
    op.drop_column('chapters', 'parent_chapter_id')
    op.alter_column('chapters', 'folder_id', nullable=False)
