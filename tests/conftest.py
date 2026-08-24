"""Shared fixtures for the backend test suite.

Runs against the same local Postgres the dev stack already uses (DATABASE_URL
from the environment) -- there's no separate test database or in-memory
sqlite, since the schema leans on Postgres-specific features
(gen_random_uuid(), tsvector, advisory locks). Each test gets its own
throwaway book via `make_book`/`make_folder`/`make_chapter`; deleting the
book at teardown cascades away everything created under it, so tests don't
need transaction-rollback machinery to stay isolated from each other or from
whatever real data already lives in the dev DB.
"""
import uuid

import pytest

from app import app as flask_app
from extensions import db
from models import User, Folder, Chapter


@pytest.fixture(scope='session')
def app():
    return flask_app


@pytest.fixture(autouse=True)
def app_context(app):
    with app.app_context():
        yield


@pytest.fixture
def cleanup():
    """Tests register root Folder ids (books) and User ids they created;
    torn down after the test body runs, success or not. Chapters are
    bulk-deleted by book_id in one statement before the book itself --
    parent_chapter_id is ON DELETE RESTRICT (not CASCADE, see models.py),
    so deleting a folder-child chapter that still has RESTRICT-referencing
    nested children would otherwise be blocked; a single multi-row DELETE
    that removes an entire self-referential chain together doesn't hit
    that, since Postgres's FK trigger checks the statement's final state,
    not each row's intermediate one."""
    created_book_ids = []
    created_user_ids = []
    yield {'books': created_book_ids, 'users': created_user_ids}
    # A failed test can leave the session needing a rollback (e.g. an
    # uncaught IntegrityError from a bad flush) -- without this, every ORM
    # call below would immediately raise PendingRollbackError and skip
    # cleanup entirely, orphaning this test's data permanently.
    db.session.rollback()
    if created_book_ids:
        db.session.query(Chapter).filter(Chapter.book_id.in_(created_book_ids)).delete(synchronize_session=False)
        db.session.commit()
    for book_id in created_book_ids:
        book = db.session.get(Folder, book_id)
        if book is not None:
            db.session.delete(book)
    db.session.commit()
    for user_id in created_user_ids:
        user = db.session.get(User, user_id)
        if user is not None:
            db.session.delete(user)
    db.session.commit()


@pytest.fixture
def user(cleanup):
    u = User(username=f'test-{uuid.uuid4().hex[:12]}', password_hash='x', is_admin=False)
    db.session.add(u)
    db.session.commit()
    cleanup['users'].append(u.id)
    return u


@pytest.fixture
def make_book(cleanup, user):
    def _make(name=None, owner=None):
        book_id = uuid.uuid4()
        book = Folder(
            id=book_id, parent_id=None, book_id=book_id, owner_id=(owner or user).id,
            name=name or f'Book {uuid.uuid4().hex[:8]}',
        )
        db.session.add(book)
        db.session.commit()
        cleanup['books'].append(book.id)
        return book
    return _make


@pytest.fixture
def make_folder():
    def _make(parent: Folder, name=None):
        folder = Folder(parent_id=parent.id, book_id=parent.book_id, name=name or f'Folder {uuid.uuid4().hex[:8]}')
        db.session.add(folder)
        db.session.commit()
        return folder
    return _make


@pytest.fixture
def make_chapter():
    def _make(*, folder: Folder | None = None, parent_chapter: Chapter | None = None, name=None):
        assert (folder is None) != (parent_chapter is None), 'exactly one of folder/parent_chapter'
        book_id = folder.book_id if folder is not None else parent_chapter.book_id
        chapter = Chapter(
            folder_id=folder.id if folder is not None else None,
            parent_chapter_id=parent_chapter.id if parent_chapter is not None else None,
            book_id=book_id,
            name=name or f'Chapter {uuid.uuid4().hex[:8]}',
        )
        db.session.add(chapter)
        db.session.commit()
        return chapter
    return _make
