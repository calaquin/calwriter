"""add resource_shares (generalizes book sharing to folders and chapters)

Revision ID: e8a4c6f19d02
Revises: c4a9d0e5f1b7
Create Date: 2026-08-22 14:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8a4c6f19d02'
down_revision: Union[str, None] = 'c4a9d0e5f1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'resource_shares',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('folder_id', sa.BigInteger(), nullable=True),
        sa.Column('chapter_id', sa.BigInteger(), nullable=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.Enum('editor', 'viewer', name='share_role'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            '(folder_id IS NOT NULL)::int + (chapter_id IS NOT NULL)::int = 1',
            name='chk_resource_shares_one_target',
        ),
        sa.ForeignKeyConstraint(['folder_id'], ['folders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('folder_id', 'user_id', name='uq_resource_shares_folder_user'),
        sa.UniqueConstraint('chapter_id', 'user_id', name='uq_resource_shares_chapter_user'),
    )
    op.create_index(op.f('ix_resource_shares_folder_id'), 'resource_shares', ['folder_id'])
    op.create_index(op.f('ix_resource_shares_chapter_id'), 'resource_shares', ['chapter_id'])
    op.create_index(op.f('ix_resource_shares_user_id'), 'resource_shares', ['user_id'])

    # A book share was always (book_id, user_id) -- migrate each row to a
    # folder-level share on that same root folder id, same role/timestamp.
    op.execute(
        """
        INSERT INTO resource_shares (folder_id, chapter_id, user_id, role, created_at)
        SELECT book_id, NULL, user_id, role::text::share_role, created_at
        FROM book_collaborators
        """
    )

    op.drop_index(op.f('ix_book_collaborators_user_id'), table_name='book_collaborators')
    op.drop_table('book_collaborators')
    sa.Enum(name='book_role').drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    book_role = sa.Enum('editor', 'viewer', name='book_role')
    book_role.create(op.get_bind(), checkfirst=True)
    op.create_table(
        'book_collaborators',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('book_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('role', book_role, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['book_id'], ['folders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('book_id', 'user_id', name='uq_book_collaborators_book_user'),
    )
    op.create_index(op.f('ix_book_collaborators_user_id'), 'book_collaborators', ['user_id'], unique=False)

    # Only whole-book shares (folder_id pointing at a root folder) round-trip;
    # sub-folder and chapter shares have no equivalent in the old model and
    # are dropped.
    op.execute(
        """
        INSERT INTO book_collaborators (book_id, user_id, role, created_at)
        SELECT rs.folder_id, rs.user_id, rs.role::text::book_role, rs.created_at
        FROM resource_shares rs
        JOIN folders f ON f.id = rs.folder_id
        WHERE rs.folder_id IS NOT NULL AND f.parent_id IS NULL
        """
    )

    op.drop_index(op.f('ix_resource_shares_user_id'), table_name='resource_shares')
    op.drop_index(op.f('ix_resource_shares_chapter_id'), table_name='resource_shares')
    op.drop_index(op.f('ix_resource_shares_folder_id'), table_name='resource_shares')
    op.drop_table('resource_shares')
    sa.Enum(name='share_role').drop(op.get_bind(), checkfirst=True)
