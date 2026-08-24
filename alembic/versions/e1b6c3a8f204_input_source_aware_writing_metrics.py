"""input-source-aware writing metrics

Revision ID: e1b6c3a8f204
Revises: 9a1e5c3d7b64
Create Date: 2026-08-24 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1b6c3a8f204'
down_revision: Union[str, None] = '9a1e5c3d7b64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing words_written values migrate as-is into words_typed -- they
    # won't be perfectly paste-clean historically, but everything from here
    # on is. Rename (not drop+add) so the data isn't lost.
    op.alter_column('chapter_writing_activity', 'words_written', new_column_name='words_typed')
    op.add_column('chapter_writing_activity', sa.Column('words_pasted', sa.Integer(), server_default='0', nullable=False))

    # Mirrors last_word_count's existing idempotent-heartbeat pattern: the
    # client now sends cumulative-since-mount typed/pasted totals instead of
    # a per-heartbeat delta, and these columns are what the server diffs
    # against (see api.api_heartbeat_chapter_presence).
    op.add_column('chapter_presence', sa.Column('last_typed_words', sa.Integer(), server_default='0', nullable=False))
    op.add_column('chapter_presence', sa.Column('last_pasted_words', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('chapter_presence', 'last_pasted_words')
    op.drop_column('chapter_presence', 'last_typed_words')
    op.drop_column('chapter_writing_activity', 'words_pasted')
    op.alter_column('chapter_writing_activity', 'words_typed', new_column_name='words_written')
