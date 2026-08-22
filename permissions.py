from flask import abort, g
from flask_login import current_user

from extensions import db
from models import ResourceShare, Chapter, Folder

ROLE_RANK = {'viewer': 0, 'editor': 1, 'owner': 2}


def _best_role(*roles: str | None) -> str | None:
    present = [r for r in roles if r is not None]
    if not present:
        return None
    return max(present, key=lambda r: ROLE_RANK[r])


def role_for_folder(folder: Folder) -> str | None:
    """Resolve the current user's role on a folder: owner of its book, else
    the highest role granted by a share on that folder or any ancestor folder
    up to (and including) the book root -- a share covers its own subtree."""
    book = folder if folder.parent_id is None else db.session.get(Folder, folder.book_id)
    if book is not None and book.owner_id == current_user.id:
        return 'owner'

    best = None
    node = folder
    while node is not None:
        share = ResourceShare.query.filter_by(folder_id=node.id, user_id=current_user.id).first()
        if share is not None:
            best = _best_role(best, share.role.value)
        if node.parent_id is None:
            break
        node = db.session.get(Folder, node.parent_id)
    return best


def role_for_chapter(chapter: Chapter) -> str | None:
    book = db.session.get(Folder, chapter.book_id)
    if book is not None and book.owner_id == current_user.id:
        return 'owner'

    direct = ResourceShare.query.filter_by(chapter_id=chapter.id, user_id=current_user.id).first()
    best = direct.role.value if direct else None

    folder = db.session.get(Folder, chapter.folder_id)
    if folder is not None:
        best = _best_role(best, role_for_folder(folder))
    return best


def accessible_book_ids() -> set[int]:
    """Root folder ids the current user has whole-book access to: books they
    own, or books with a share directly on the root folder. Doesn't include
    books where they only have a narrower sub-folder/chapter share -- see
    shared_items() for those."""
    if 'accessible_book_ids' not in g:
        owned = Folder.query.filter_by(parent_id=None, owner_id=current_user.id).with_entities(Folder.id)
        shared = (
            Folder.query.join(ResourceShare, ResourceShare.folder_id == Folder.id)
            .filter(Folder.parent_id.is_(None), ResourceShare.user_id == current_user.id)
            .with_entities(Folder.id)
        )
        g.accessible_book_ids = {row.id for row in owned} | {row.id for row in shared}
    return g.accessible_book_ids


def shared_items() -> tuple[list[Folder], list[Chapter]]:
    """Sub-folders and chapters shared directly with the current user, for
    books they don't already have whole-book access to (see
    accessible_book_ids) -- these surface as their own top-level sidebar
    entries rather than inside a book tree the user can't otherwise see."""
    book_ids = accessible_book_ids()
    folder_shares = ResourceShare.query.filter(
        ResourceShare.user_id == current_user.id, ResourceShare.folder_id.isnot(None)
    ).all()
    folders = [
        s.folder
        for s in folder_shares
        if s.folder is not None and s.folder.parent_id is not None and s.folder.book_id not in book_ids
    ]
    chapter_shares = ResourceShare.query.filter(
        ResourceShare.user_id == current_user.id, ResourceShare.chapter_id.isnot(None)
    ).all()
    chapters = [s.chapter for s in chapter_shares if s.chapter is not None and s.chapter.book_id not in book_ids]
    return folders, chapters


def require_book_access(book_id: int, min_role: str = 'viewer') -> Folder:
    """Load a book (root folder) and assert current_user has >= min_role on it.

    404s (not 403) when the user has no relationship to the book at all, so
    its existence isn't revealed to people it isn't shared with.
    """
    book = Folder.query.filter_by(id=book_id, parent_id=None).first()
    if book is None:
        abort(404)
    role = role_for_folder(book)
    if role is None:
        abort(404)
    if ROLE_RANK[role] < ROLE_RANK[min_role]:
        abort(403)
    return book


def require_folder_access(folder_id: int, min_role: str = 'viewer') -> Folder:
    folder = Folder.query.get_or_404(folder_id)
    role = role_for_folder(folder)
    if role is None:
        abort(404)
    if ROLE_RANK[role] < ROLE_RANK[min_role]:
        abort(403)
    return folder


def require_chapter_access(chapter_id: int, min_role: str = 'viewer') -> Chapter:
    chapter = Chapter.query.get_or_404(chapter_id)
    role = role_for_chapter(chapter)
    if role is None:
        abort(404)
    if ROLE_RANK[role] < ROLE_RANK[min_role]:
        abort(403)
    return chapter


def require_folder_share_management(folder: Folder) -> None:
    """A folder's shares can be managed by anyone with editor+ access to it,
    except a book root, which stays owner-only -- preserves the original
    book-sharing permission rather than loosening it for this new capability."""
    min_role = 'owner' if folder.parent_id is None else 'editor'
    role = role_for_folder(folder)
    if role is None:
        abort(404)
    if ROLE_RANK[role] < ROLE_RANK[min_role]:
        abort(403)


def require_chapter_share_management(chapter: Chapter) -> None:
    role = role_for_chapter(chapter)
    if role is None:
        abort(404)
    if ROLE_RANK[role] < ROLE_RANK['editor']:
        abort(403)
