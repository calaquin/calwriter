"""add customizable dark palette colors

Revision ID: d6f1a8c2b903
Revises: 4cf412eecab4
Create Date: 2026-08-21 19:08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd6f1a8c2b903'
down_revision: Union[str, None] = '4cf412eecab4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_settings',
        sa.Column('dark_sidebar_color', sa.String(length=16), nullable=False, server_default='#333333'),
    )
    op.add_column(
        'user_settings',
        sa.Column('dark_text_color', sa.String(length=16), nullable=False, server_default='#eeeeee'),
    )
    op.add_column(
        'user_settings',
        sa.Column('dark_bg_color', sa.String(length=16), nullable=False, server_default='#222222'),
    )
    op.add_column(
        'user_settings',
        sa.Column('dark_toolbar_color', sa.String(length=16), nullable=False, server_default='#555555'),
    )
    op.add_column(
        'user_settings',
        sa.Column('dark_editor_color', sa.String(length=16), nullable=False, server_default='#444444'),
    )


def downgrade() -> None:
    op.drop_column('user_settings', 'dark_editor_color')
    op.drop_column('user_settings', 'dark_toolbar_color')
    op.drop_column('user_settings', 'dark_bg_color')
    op.drop_column('user_settings', 'dark_text_color')
    op.drop_column('user_settings', 'dark_sidebar_color')
