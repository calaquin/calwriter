"""add show_book_color

Revision ID: 9f88af299878
Revises: d4e6b8a1f930
Create Date: 2026-08-23 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f88af299878'
down_revision: Union[str, None] = 'd4e6b8a1f930'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('folders', sa.Column('show_book_color', sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column('chapters', sa.Column('show_book_color', sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    op.drop_column('chapters', 'show_book_color')
    op.drop_column('folders', 'show_book_color')
