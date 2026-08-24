"""add user-local IANA timezone

Revision ID: a6c4e2f8b105
Revises: f4a2d9c6b731
Create Date: 2026-08-24 00:00:00

Historical chapter_writing_activity rows are deliberately not rewritten:
they retain valid totals, but the old aggregate-only schema has no raw UTC
event timestamp from which a truthful local date/hour could be reconstructed.
Timezone-aware bucketing begins with this migration's application.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a6c4e2f8b105'
down_revision: Union[str, None] = 'f4a2d9c6b731'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('timezone', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'timezone')
