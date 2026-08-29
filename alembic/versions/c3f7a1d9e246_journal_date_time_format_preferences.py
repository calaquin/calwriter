"""journal date/time format preferences

Revision ID: c3f7a1d9e246
Revises: b6e2f9a4c817
Create Date: 2026-08-29 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3f7a1d9e246'
down_revision: Union[str, None] = 'b6e2f9a4c817'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('journal_date_format', sa.String(32), server_default='long_month_day_year', nullable=False),
    )
    op.add_column(
        'users',
        sa.Column('journal_time_format', sa.String(16), server_default='12_hour', nullable=False),
    )
    op.create_check_constraint(
        'chk_users_journal_date_format',
        'users',
        "journal_date_format IN ("
        "'long_month_day_year', 'short_month_day_year', 'day_long_month_year', 'day_short_month_year', "
        "'us_numeric', 'day_first_numeric', 'iso', 'weekday_long')",
    )
    op.create_check_constraint(
        'chk_users_journal_time_format',
        'users',
        "journal_time_format IN ('12_hour', '24_hour')",
    )


def downgrade() -> None:
    op.drop_constraint('chk_users_journal_time_format', 'users', type_='check')
    op.drop_constraint('chk_users_journal_date_format', 'users', type_='check')
    op.drop_column('users', 'journal_time_format')
    op.drop_column('users', 'journal_date_format')
