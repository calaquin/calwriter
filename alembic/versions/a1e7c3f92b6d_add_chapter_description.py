"""add chapter description

Revision ID: a1e7c3f92b6d
Revises: d6f1a8c2b903
Create Date: 2026-08-21 20:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1e7c3f92b6d'
down_revision: Union[str, None] = 'd6f1a8c2b903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'chapters',
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
    )


def downgrade() -> None:
    op.drop_column('chapters', 'description')
