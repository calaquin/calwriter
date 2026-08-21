"""add invites

Revision ID: c4a9d0e5f1b7
Revises: b7e2f6a91c3d
Create Date: 2026-08-21 22:35:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4a9d0e5f1b7'
down_revision: Union[str, None] = 'b7e2f6a91c3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'invites',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('created_by_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_by_id', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['used_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token', name='uq_invites_token'),
    )
    op.create_index('ix_invites_token', 'invites', ['token'])


def downgrade() -> None:
    op.drop_index('ix_invites_token', table_name='invites')
    op.drop_table('invites')
