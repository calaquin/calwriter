"""convert ids to uuid

Revision ID: 642834d96895
Revises: 9f88af299878
Create Date: 2026-08-23 00:00:00

Converts every table's primary key (and every foreign key pointing at one)
from BigInteger to native Postgres UUID, generated via the built-in
gen_random_uuid() (PG13+, no pgcrypto extension needed). Also converts the
six ARRAY(BigInteger) id-list columns on user_settings.

Structured as two global phases rather than table-by-table complete cycles:
Phase A adds shadow uuid_* columns and backfills them (a child's backfill
needs both the parent's old bigint id and new uuid_id present at once, and
user_settings's arrays depend on folders/chapters/goals all having their new
id populated -- so this can't be done one table at a time start-to-finish).
Phase B drops the old structure and renames the shadow columns into place.

This is a one-shot, in-practice-irreversible migration: original bigint id
values are destroyed and cannot be recovered by downgrade(). See its body.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '642834d96895'
down_revision: Union[str, None] = '9f88af299878'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------- Phase A --
    # Add uuid_* shadow columns and backfill them, in dependency order.

    # users
    op.add_column('users', sa.Column(
        'uuid_id', postgresql.UUID(as_uuid=True), nullable=False,
        server_default=sa.text('gen_random_uuid()'),
    ))

    # user_settings.user_id (scalar -- mirrors users.id, not independently generated)
    op.add_column('user_settings', sa.Column('uuid_user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE user_settings s SET uuid_user_id = u.uuid_id FROM users u WHERE s.user_id = u.id")
    op.alter_column('user_settings', 'uuid_user_id', nullable=False)

    # folders (self-referential parent_id/book_id + owner_id -> users)
    op.add_column('folders', sa.Column(
        'uuid_id', postgresql.UUID(as_uuid=True), nullable=False,
        server_default=sa.text('gen_random_uuid()'),
    ))
    op.add_column('folders', sa.Column('uuid_parent_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('folders', sa.Column('uuid_book_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('folders', sa.Column('uuid_owner_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE folders c SET uuid_parent_id = p.uuid_id FROM folders p WHERE c.parent_id = p.id")
    op.execute("UPDATE folders c SET uuid_book_id = b.uuid_id FROM folders b WHERE c.book_id = b.id")
    op.execute("UPDATE folders f SET uuid_owner_id = u.uuid_id FROM users u WHERE f.owner_id = u.id")
    op.alter_column('folders', 'uuid_book_id', nullable=False)

    # chapters
    op.add_column('chapters', sa.Column(
        'uuid_id', postgresql.UUID(as_uuid=True), nullable=False,
        server_default=sa.text('gen_random_uuid()'),
    ))
    op.add_column('chapters', sa.Column('uuid_folder_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('chapters', sa.Column('uuid_book_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE chapters c SET uuid_folder_id = f.uuid_id FROM folders f WHERE c.folder_id = f.id")
    op.execute("UPDATE chapters c SET uuid_book_id = f.uuid_id FROM folders f WHERE c.book_id = f.id")
    op.alter_column('chapters', 'uuid_folder_id', nullable=False)
    op.alter_column('chapters', 'uuid_book_id', nullable=False)

    # chapter_versions
    op.add_column('chapter_versions', sa.Column(
        'uuid_id', postgresql.UUID(as_uuid=True), nullable=False,
        server_default=sa.text('gen_random_uuid()'),
    ))
    op.add_column('chapter_versions', sa.Column('uuid_chapter_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE chapter_versions cv SET uuid_chapter_id = c.uuid_id FROM chapters c WHERE cv.chapter_id = c.id")
    op.alter_column('chapter_versions', 'uuid_chapter_id', nullable=False)

    # chapter_presence
    op.add_column('chapter_presence', sa.Column(
        'uuid_id', postgresql.UUID(as_uuid=True), nullable=False,
        server_default=sa.text('gen_random_uuid()'),
    ))
    op.add_column('chapter_presence', sa.Column('uuid_chapter_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('chapter_presence', sa.Column('uuid_user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE chapter_presence cp SET uuid_chapter_id = c.uuid_id FROM chapters c WHERE cp.chapter_id = c.id")
    op.execute("UPDATE chapter_presence cp SET uuid_user_id = u.uuid_id FROM users u WHERE cp.user_id = u.id")
    op.alter_column('chapter_presence', 'uuid_chapter_id', nullable=False)
    op.alter_column('chapter_presence', 'uuid_user_id', nullable=False)

    # resource_shares
    op.add_column('resource_shares', sa.Column(
        'uuid_id', postgresql.UUID(as_uuid=True), nullable=False,
        server_default=sa.text('gen_random_uuid()'),
    ))
    op.add_column('resource_shares', sa.Column('uuid_folder_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('resource_shares', sa.Column('uuid_chapter_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('resource_shares', sa.Column('uuid_user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE resource_shares rs SET uuid_folder_id = f.uuid_id FROM folders f WHERE rs.folder_id = f.id")
    op.execute("UPDATE resource_shares rs SET uuid_chapter_id = c.uuid_id FROM chapters c WHERE rs.chapter_id = c.id")
    op.execute("UPDATE resource_shares rs SET uuid_user_id = u.uuid_id FROM users u WHERE rs.user_id = u.id")
    op.alter_column('resource_shares', 'uuid_user_id', nullable=False)

    # invites
    op.add_column('invites', sa.Column(
        'uuid_id', postgresql.UUID(as_uuid=True), nullable=False,
        server_default=sa.text('gen_random_uuid()'),
    ))
    op.add_column('invites', sa.Column('uuid_created_by_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('invites', sa.Column('uuid_used_by_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE invites i SET uuid_created_by_id = u.uuid_id FROM users u WHERE i.created_by_id = u.id")
    op.execute("UPDATE invites i SET uuid_used_by_id = u.uuid_id FROM users u WHERE i.used_by_id = u.id")
    op.alter_column('invites', 'uuid_created_by_id', nullable=False)

    # goals
    op.add_column('goals', sa.Column(
        'uuid_id', postgresql.UUID(as_uuid=True), nullable=False,
        server_default=sa.text('gen_random_uuid()'),
    ))
    op.add_column('goals', sa.Column('uuid_user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('goals', sa.Column('uuid_folder_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('goals', sa.Column('uuid_chapter_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE goals g SET uuid_user_id = u.uuid_id FROM users u WHERE g.user_id = u.id")
    op.execute("UPDATE goals g SET uuid_folder_id = f.uuid_id FROM folders f WHERE g.folder_id = f.id")
    op.execute("UPDATE goals g SET uuid_chapter_id = c.uuid_id FROM chapters c WHERE g.chapter_id = c.id")
    op.alter_column('goals', 'uuid_user_id', nullable=False)

    # goal_period_history
    op.add_column('goal_period_history', sa.Column(
        'uuid_id', postgresql.UUID(as_uuid=True), nullable=False,
        server_default=sa.text('gen_random_uuid()'),
    ))
    op.add_column('goal_period_history', sa.Column('uuid_goal_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE goal_period_history h SET uuid_goal_id = g.uuid_id FROM goals g WHERE h.goal_id = g.id")
    op.alter_column('goal_period_history', 'uuid_goal_id', nullable=False)

    # user_settings arrays -- last, depends on folders/chapters/goals uuid_id
    array_cols = {
        'open_book_ids': 'folders', 'closed_folder_ids': 'folders', 'book_order': 'folders',
        'closed_chapter_ids': 'chapters',
        'hidden_goal_ids': 'goals', 'goal_order': 'goals',
    }
    for col, ref_table in array_cols.items():
        op.add_column('user_settings', sa.Column(
            f'uuid_{col}', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True,
        ))
        op.execute(f"""
            UPDATE user_settings s SET uuid_{col} = COALESCE(
              (SELECT array_agg(r.uuid_id ORDER BY ord)
               FROM unnest(s.{col}) WITH ORDINALITY AS t(old_id, ord)
               JOIN {ref_table} r ON r.id = t.old_id),
              ARRAY[]::uuid[])
        """)
        op.alter_column('user_settings', f'uuid_{col}', nullable=False)

    # ---------------------------------------------------------- Phase B --
    # Drop old structure (by exact name, verified against the live DB),
    # rename shadow columns into place, re-add constraints/indexes.

    # B1: constraints that would block dropping old columns
    op.drop_constraint('chk_root_owner', 'folders', type_='check')
    op.drop_constraint('chk_resource_shares_one_target', 'resource_shares', type_='check')
    op.drop_constraint('chk_goals_one_target', 'goals', type_='check')

    op.drop_constraint('uq_folders_parent_name', 'folders', type_='unique')
    op.drop_constraint('uq_chapters_folder_name', 'chapters', type_='unique')
    op.drop_constraint('uq_chapter_presence_chapter_user', 'chapter_presence', type_='unique')
    op.drop_constraint('uq_resource_shares_folder_user', 'resource_shares', type_='unique')
    op.drop_constraint('uq_resource_shares_chapter_user', 'resource_shares', type_='unique')

    for tbl, name in [
        ('folders', 'ix_folders_parent_id'), ('folders', 'ix_folders_book_id'),
        ('chapters', 'ix_chapters_folder_id'), ('chapters', 'ix_chapters_book_id'),
        ('chapter_versions', 'ix_chapter_versions_chapter_id'),
        ('chapter_presence', 'ix_chapter_presence_chapter_id'),
        ('resource_shares', 'ix_resource_shares_folder_id'),
        ('resource_shares', 'ix_resource_shares_chapter_id'),
        ('resource_shares', 'ix_resource_shares_user_id'),
        ('goals', 'ix_goals_user_id'), ('goals', 'ix_goals_folder_id'), ('goals', 'ix_goals_chapter_id'),
        ('goal_period_history', 'ix_goal_period_history_goal_id'),
    ]:
        op.drop_index(name, table_name=tbl)

    for tbl, name in [
        ('folders', 'folders_parent_id_fkey'), ('folders', 'folders_book_id_fkey'),
        ('folders', 'folders_owner_id_fkey'),
        ('chapters', 'chapters_folder_id_fkey'), ('chapters', 'chapters_book_id_fkey'),
        ('chapter_versions', 'chapter_versions_chapter_id_fkey'),
        ('chapter_presence', 'chapter_presence_chapter_id_fkey'),
        ('chapter_presence', 'chapter_presence_user_id_fkey'),
        ('resource_shares', 'resource_shares_folder_id_fkey'),
        ('resource_shares', 'resource_shares_chapter_id_fkey'),
        ('resource_shares', 'resource_shares_user_id_fkey'),
        ('invites', 'invites_created_by_id_fkey'), ('invites', 'invites_used_by_id_fkey'),
        ('user_settings', 'user_settings_user_id_fkey'),
        ('goals', 'goals_user_id_fkey'), ('goals', 'goals_folder_id_fkey'), ('goals', 'goals_chapter_id_fkey'),
        ('goal_period_history', 'goal_period_history_goal_id_fkey'),
    ]:
        op.drop_constraint(name, tbl, type_='foreignkey')

    # B2: drop old bigint columns (auto-drops their owned sequences and old PKs)
    op.drop_column('users', 'id')
    op.drop_column('folders', 'id')
    op.drop_column('folders', 'parent_id')
    op.drop_column('folders', 'book_id')
    op.drop_column('folders', 'owner_id')
    op.drop_column('chapters', 'id')
    op.drop_column('chapters', 'folder_id')
    op.drop_column('chapters', 'book_id')
    op.drop_column('chapter_versions', 'id')
    op.drop_column('chapter_versions', 'chapter_id')
    op.drop_column('chapter_presence', 'id')
    op.drop_column('chapter_presence', 'chapter_id')
    op.drop_column('chapter_presence', 'user_id')
    op.drop_column('resource_shares', 'id')
    op.drop_column('resource_shares', 'folder_id')
    op.drop_column('resource_shares', 'chapter_id')
    op.drop_column('resource_shares', 'user_id')
    op.drop_column('invites', 'id')
    op.drop_column('invites', 'created_by_id')
    op.drop_column('invites', 'used_by_id')
    op.drop_column('user_settings', 'user_id')
    for col in array_cols:
        op.drop_column('user_settings', col)
    op.drop_column('goals', 'id')
    op.drop_column('goals', 'user_id')
    op.drop_column('goals', 'folder_id')
    op.drop_column('goals', 'chapter_id')
    op.drop_column('goal_period_history', 'id')
    op.drop_column('goal_period_history', 'goal_id')

    # B3: rename uuid_* -> final names
    op.alter_column('users', 'uuid_id', new_column_name='id')

    op.alter_column('folders', 'uuid_id', new_column_name='id')
    op.alter_column('folders', 'uuid_parent_id', new_column_name='parent_id')
    op.alter_column('folders', 'uuid_book_id', new_column_name='book_id')
    op.alter_column('folders', 'uuid_owner_id', new_column_name='owner_id')

    op.alter_column('chapters', 'uuid_id', new_column_name='id')
    op.alter_column('chapters', 'uuid_folder_id', new_column_name='folder_id')
    op.alter_column('chapters', 'uuid_book_id', new_column_name='book_id')

    op.alter_column('chapter_versions', 'uuid_id', new_column_name='id')
    op.alter_column('chapter_versions', 'uuid_chapter_id', new_column_name='chapter_id')

    op.alter_column('chapter_presence', 'uuid_id', new_column_name='id')
    op.alter_column('chapter_presence', 'uuid_chapter_id', new_column_name='chapter_id')
    op.alter_column('chapter_presence', 'uuid_user_id', new_column_name='user_id')

    op.alter_column('resource_shares', 'uuid_id', new_column_name='id')
    op.alter_column('resource_shares', 'uuid_folder_id', new_column_name='folder_id')
    op.alter_column('resource_shares', 'uuid_chapter_id', new_column_name='chapter_id')
    op.alter_column('resource_shares', 'uuid_user_id', new_column_name='user_id')

    op.alter_column('invites', 'uuid_id', new_column_name='id')
    op.alter_column('invites', 'uuid_created_by_id', new_column_name='created_by_id')
    op.alter_column('invites', 'uuid_used_by_id', new_column_name='used_by_id')

    op.alter_column('user_settings', 'uuid_user_id', new_column_name='user_id')
    for col in array_cols:
        op.alter_column('user_settings', f'uuid_{col}', new_column_name=col)

    op.alter_column('goals', 'uuid_id', new_column_name='id')
    op.alter_column('goals', 'uuid_user_id', new_column_name='user_id')
    op.alter_column('goals', 'uuid_folder_id', new_column_name='folder_id')
    op.alter_column('goals', 'uuid_chapter_id', new_column_name='chapter_id')

    op.alter_column('goal_period_history', 'uuid_id', new_column_name='id')
    op.alter_column('goal_period_history', 'uuid_goal_id', new_column_name='goal_id')

    # B4: primary keys
    for tbl, col in [
        ('users', 'id'), ('folders', 'id'), ('chapters', 'id'), ('chapter_versions', 'id'),
        ('chapter_presence', 'id'), ('resource_shares', 'id'), ('invites', 'id'),
        ('user_settings', 'user_id'), ('goals', 'id'), ('goal_period_history', 'id'),
    ]:
        op.create_primary_key(f'{tbl}_pkey', tbl, [col])

    # B5: foreign keys (must follow B4)
    op.create_foreign_key('folders_parent_id_fkey', 'folders', 'folders', ['parent_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('folders_book_id_fkey', 'folders', 'folders', ['book_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('folders_owner_id_fkey', 'folders', 'users', ['owner_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('chapters_folder_id_fkey', 'chapters', 'folders', ['folder_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('chapters_book_id_fkey', 'chapters', 'folders', ['book_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('chapter_versions_chapter_id_fkey', 'chapter_versions', 'chapters', ['chapter_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('chapter_presence_chapter_id_fkey', 'chapter_presence', 'chapters', ['chapter_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('chapter_presence_user_id_fkey', 'chapter_presence', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('resource_shares_folder_id_fkey', 'resource_shares', 'folders', ['folder_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('resource_shares_chapter_id_fkey', 'resource_shares', 'chapters', ['chapter_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('resource_shares_user_id_fkey', 'resource_shares', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('invites_created_by_id_fkey', 'invites', 'users', ['created_by_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('invites_used_by_id_fkey', 'invites', 'users', ['used_by_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('user_settings_user_id_fkey', 'user_settings', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('goals_user_id_fkey', 'goals', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('goals_folder_id_fkey', 'goals', 'folders', ['folder_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('goals_chapter_id_fkey', 'goals', 'chapters', ['chapter_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('goal_period_history_goal_id_fkey', 'goal_period_history', 'goals', ['goal_id'], ['id'], ondelete='CASCADE')

    # B6: unique + check constraints
    op.create_unique_constraint('uq_folders_parent_name', 'folders', ['parent_id', 'name'])
    op.create_unique_constraint('uq_chapters_folder_name', 'chapters', ['folder_id', 'name'])
    op.create_unique_constraint('uq_chapter_presence_chapter_user', 'chapter_presence', ['chapter_id', 'user_id'])
    op.create_unique_constraint('uq_resource_shares_folder_user', 'resource_shares', ['folder_id', 'user_id'])
    op.create_unique_constraint('uq_resource_shares_chapter_user', 'resource_shares', ['chapter_id', 'user_id'])
    op.create_check_constraint('chk_root_owner', 'folders', 'parent_id IS NOT NULL OR owner_id IS NOT NULL')
    op.create_check_constraint(
        'chk_resource_shares_one_target', 'resource_shares',
        '(folder_id IS NOT NULL)::int + (chapter_id IS NOT NULL)::int = 1',
    )
    op.create_check_constraint(
        'chk_goals_one_target', 'goals',
        '(folder_id IS NOT NULL)::int + (chapter_id IS NOT NULL)::int = 1',
    )

    # B7: indexes (original names)
    op.create_index('ix_folders_parent_id', 'folders', ['parent_id'])
    op.create_index('ix_folders_book_id', 'folders', ['book_id'])
    op.create_index('ix_chapters_folder_id', 'chapters', ['folder_id'])
    op.create_index('ix_chapters_book_id', 'chapters', ['book_id'])
    op.create_index('ix_chapter_versions_chapter_id', 'chapter_versions', ['chapter_id'])
    op.create_index('ix_chapter_presence_chapter_id', 'chapter_presence', ['chapter_id'])
    op.create_index('ix_resource_shares_folder_id', 'resource_shares', ['folder_id'])
    op.create_index('ix_resource_shares_chapter_id', 'resource_shares', ['chapter_id'])
    op.create_index('ix_resource_shares_user_id', 'resource_shares', ['user_id'])
    op.create_index('ix_goals_user_id', 'goals', ['user_id'])
    op.create_index('ix_goals_folder_id', 'goals', ['folder_id'])
    op.create_index('ix_goals_chapter_id', 'goals', ['chapter_id'])
    op.create_index('ix_goal_period_history_goal_id', 'goal_period_history', ['goal_id'])


def downgrade() -> None:
    raise NotImplementedError(
        "This migration is irreversible in practice: original bigint ids are "
        "destroyed, and a lossy downgrade would leave the schema out of sync "
        "with the UUID-typed application code that ships alongside it -- the "
        "app would stay broken either way. Restore from a pre-migration "
        "pg_dump instead."
    )
