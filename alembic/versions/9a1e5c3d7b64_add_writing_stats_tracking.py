"""add writing stats tracking

Revision ID: 9a1e5c3d7b64
Revises: 4c7a358e0923
Create Date: 2026-08-23 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '9a1e5c3d7b64'
down_revision: Union[str, None] = '4c7a358e0923'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chapter_presence', sa.Column('last_word_count', sa.Integer(), nullable=True))

    op.add_column('chapters', sa.Column('version_count', sa.Integer(), server_default='0', nullable=False))

    op.create_table(
        'chapter_writing_activity',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chapter_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('hour_of_day', sa.Integer(), nullable=False),
        sa.Column('active_seconds', sa.Integer(), server_default='0', nullable=False),
        sa.Column('words_written', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id', 'chapter_id', 'date', 'hour_of_day',
            name='uq_chapter_writing_activity_user_chapter_date_hour',
        ),
        sa.CheckConstraint('hour_of_day >= 0 AND hour_of_day <= 23', name='chk_chapter_writing_activity_hour_range'),
    )
    op.create_index('ix_chapter_writing_activity_user_id', 'chapter_writing_activity', ['user_id'])
    op.create_index('ix_chapter_writing_activity_chapter_id', 'chapter_writing_activity', ['chapter_id'])


def downgrade() -> None:
    op.drop_index('ix_chapter_writing_activity_chapter_id', table_name='chapter_writing_activity')
    op.drop_index('ix_chapter_writing_activity_user_id', table_name='chapter_writing_activity')
    op.drop_table('chapter_writing_activity')
    op.drop_column('chapters', 'version_count')
    op.drop_column('chapter_presence', 'last_word_count')
