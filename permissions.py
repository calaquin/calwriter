from flask import abort, g
from flask_login import current_user

from models import BookCollaborator, Chapter, Folder

ROLE_RANK = {'viewer': 0, 'editor': 1, 'owner': 2}


def _role_for(book: Folder) -> str | None:
    if book.owner_id == current_user.id:
        return 'owner'
    collab = BookCollaborator.query.filter_by(book_id=book.id, user_id=current_user.id).first()
    return collab.role.value if collab else None


def accessible_book_ids() -> set[int]:
    """All book (root folder) ids the current user can see, cached per-request."""
    if 'accessible_book_ids' not in g:
        owned = Folder.query.filter_by(parent_id=None, owner_id=current_user.id).with_entities(Folder.id)
        shared = (
            Folder.query.join(BookCollaborator, BookCollaborator.book_id == Folder.id)
            .filter(Folder.parent_id.is_(None), BookCollaborator.user_id == current_user.id)
            .with_entities(Folder.id)
        )
        g.accessible_book_ids = {row.id for row in owned} | {row.id for row in shared}
    return g.accessible_book_ids


def require_book_access(book_id: int, min_role: str = 'viewer') -> Folder:
    """Load a book (root folder) and assert current_user has >= min_role on it.

    404s (not 403) when the user has no relationship to the book at all, so
    its existence isn't revealed to people it isn't shared with.
    """
    book = Folder.query.filter_by(id=book_id, parent_id=None).first()
    if book is None:
        abort(404)
    role = _role_for(book)
    if role is None:
        abort(404)
    if ROLE_RANK[role] < ROLE_RANK[min_role]:
        abort(403)
    return book


def require_folder_access(folder_id: int, min_role: str = 'viewer') -> Folder:
    folder = Folder.query.get_or_404(folder_id)
    require_book_access(folder.book_id, min_role)
    return folder


def require_chapter_access(chapter_id: int, min_role: str = 'viewer') -> Chapter:
    chapter = Chapter.query.get_or_404(chapter_id)
    require_book_access(chapter.book_id, min_role)
    return chapter
