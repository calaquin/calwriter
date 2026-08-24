"""add user-wide editor stats visibility settings

Revision ID: b2d7e4f9a106
Revises: a6c4e2f8b105
Create Date: 2026-08-24 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2d7e4f9a106'
down_revision: Union[str, None] = 'a6c4e2f8b105'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_settings',
        sa.Column('show_word_count', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        'user_settings',
        sa.Column('show_average_wpm', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('user_settings', 'show_average_wpm')
    op.drop_column('user_settings', 'show_word_count')
