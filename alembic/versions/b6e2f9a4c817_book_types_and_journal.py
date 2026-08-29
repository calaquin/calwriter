"""book types and journal v1

Revision ID: b6e2f9a4c817
Revises: a4d8c1f7b930
Create Date: 2026-08-29 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b6e2f9a4c817'
down_revision: Union[str, None] = 'a4d8c1f7b930'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Book Type: nullable on every Folder row (application logic treats a
    # root/Book row's NULL as unmigrated, never as a fifth type -- see
    # Folder.book_type's docstring), backfilled below for existing Books.
    op.add_column('folders', sa.Column('book_type', sa.String(32), nullable=True))
    op.create_check_constraint(
        'chk_folders_book_type',
        'folders',
        "book_type IS NULL OR book_type IN ('general', 'novel', 'journal', 'documentation')",
    )
    op.execute("UPDATE folders SET book_type = 'general' WHERE parent_id IS NULL")

    # Journal organization metadata (year/month Folders).
    op.add_column('folders', sa.Column('journal_year', sa.Integer(), nullable=True))
    op.add_column('folders', sa.Column('journal_month', sa.Integer(), nullable=True))
    op.create_check_constraint(
        'chk_folders_journal_month_range',
        'folders',
        'journal_month IS NULL OR (journal_month >= 1 AND journal_month <= 12)',
    )
    op.create_check_constraint(
        'chk_folders_journal_month_requires_year',
        'folders',
        'journal_month IS NULL OR journal_year IS NOT NULL',
    )
    # Partial: an ordinary Folder's NULL/NULL row never participates in
    # either uniqueness check, only this Book's own generated year/month
    # Folders (at most one canonical row per period per Book).
    op.create_index(
        'uq_folders_journal_year', 'folders', ['book_id', 'journal_year'],
        unique=True, postgresql_where=sa.text('journal_year IS NOT NULL AND journal_month IS NULL'),
    )
    op.create_index(
        'uq_folders_journal_year_month', 'folders', ['book_id', 'journal_year', 'journal_month'],
        unique=True, postgresql_where=sa.text('journal_year IS NOT NULL AND journal_month IS NOT NULL'),
    )

    # Journal day metadata (Chapter.journal_date) -- "one Journal Chapter per
    # calendar day per Book", independent of the Chapter's current name/
    # Folder/nesting position.
    op.add_column('chapters', sa.Column('journal_date', sa.Date(), nullable=True))
    op.create_index(
        'uq_chapters_journal_date', 'chapters', ['book_id', 'journal_date'],
        unique=True, postgresql_where=sa.text('journal_date IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_chapters_journal_date', table_name='chapters')
    op.drop_column('chapters', 'journal_date')

    op.drop_index('uq_folders_journal_year_month', table_name='folders')
    op.drop_index('uq_folders_journal_year', table_name='folders')
    op.drop_constraint('chk_folders_journal_month_requires_year', 'folders', type_='check')
    op.drop_constraint('chk_folders_journal_month_range', 'folders', type_='check')
    op.drop_column('folders', 'journal_month')
    op.drop_column('folders', 'journal_year')

    op.drop_constraint('chk_folders_book_type', 'folders', type_='check')
    op.drop_column('folders', 'book_type')
