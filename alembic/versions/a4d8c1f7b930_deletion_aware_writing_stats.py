"""deletion-aware writing stats

Revision ID: a4d8c1f7b930
Revises: b2d7e4f9a106
Create Date: 2026-08-29 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4d8c1f7b930'
down_revision: Union[str, None] = 'b2d7e4f9a106'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Historical rows have no way to know how many words were ever deleted
    # from them -- 0 is the only honest default, matching words_typed/
    # words_pasted's own default when they were introduced.
    op.add_column('chapter_writing_activity', sa.Column('words_deleted', sa.Integer(), server_default='0', nullable=False))

    # Same idempotent-heartbeat-baseline pattern as last_typed_words/
    # last_pasted_words (see e1b6c3a8f204): the client sends a cumulative
    # deletedWordsTotal, and this is what the server diffs it against.
    op.add_column('chapter_presence', sa.Column('last_deleted_words', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('chapter_presence', 'last_deleted_words')
    op.drop_column('chapter_writing_activity', 'words_deleted')
