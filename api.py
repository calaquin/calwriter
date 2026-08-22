"""JSON API backing the React frontend (frontend/). Addressed by id, not
name-path -- this is what lets routing avoid any path-traversal concerns."""
import datetime
import os
import secrets
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user, login_user, logout_user
from flask_wtf.csrf import generate_csrf
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, csrf
from models import (
    User,
    UserSettings,
    Folder,
    Chapter,
    ChapterVersion,
    ChapterPresence,
    ResourceShare,
    ShareRole,
    Invite,
    Goal,
    GoalType,
    GoalCadence,
    GoalPeriodHistory,
)
from permissions import (
    accessible_book_ids,
    shared_items,
    require_book_access,
    require_folder_access,
    require_chapter_access,
    require_folder_share_management,
    require_chapter_share_management,
    role_for_folder,
    role_for_chapter,
)
from services import (
    VERSION,
    clean_name,
    render_chapter_docx,
    render_book_docx,
    render_chapter_rtf,
    render_folder_rtf,
    render_folder_docx,
    render_folder_markdown,
    render_folder_txt,
    html_to_markdown,
    folder_chapters_recursive,
    get_user_settings,
    descendant_folder_ids,
    next_folder_position,
    next_chapter_position,
    create_book,
    ordered_accessible_books,
    sanitize_html,
    html_to_text,
    prune_words_per_day,
    export_books_zip,
    import_books_zip,
    snapshot_chapter_version,
    advance_goal_period,
    resource_word_count,
    resource_completed_chapter_count,
    advance_date_by_cadence,
)

api_bp = Blueprint('api', __name__, url_prefix='/api')


def error(message, status=400):
    return jsonify({'error': message}), status


def export_filename(book: Folder, name: str, ext: str) -> str:
    parts = [book.name] + ([book.author] if book.author else []) + [name]
    return " - ".join(parts) + f".{ext}"


def _matches_updated_at(chapter: Chapter, expected: str) -> bool:
    """Optimistic-concurrency check: does `expected` (an ISO timestamp the
    client last saw) still match the chapter's current updated_at? A >1s
    tolerance absorbs float/precision drift between JS and Postgres timestamps
    without masking a real concurrent write, which will differ by much more."""
    try:
        expected_dt = datetime.datetime.fromisoformat(str(expected).replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return False
    actual_dt = chapter.updated_at
    if actual_dt.tzinfo is None:
        actual_dt = actual_dt.replace(tzinfo=datetime.timezone.utc)
    if expected_dt.tzinfo is None:
        expected_dt = expected_dt.replace(tzinfo=datetime.timezone.utc)
    return abs((actual_dt - expected_dt).total_seconds()) <= 1


def book_to_dict(book: Folder) -> dict:
    return {
        'id': book.id,
        'name': book.name,
        'description': book.description,
        'author': book.author,
        'color': book.color,
        'role': role_for_folder(book),
        'createdAt': book.created_at.isoformat(),
        'updatedAt': book.updated_at.isoformat(),
    }


def folder_to_dict(folder: Folder) -> dict:
    parent_accessible = False
    if folder.parent_id is not None:
        parent = db.session.get(Folder, folder.parent_id)
        parent_accessible = parent is not None and role_for_folder(parent) is not None
    return {
        'id': folder.id,
        'bookId': folder.book_id,
        'parentId': folder.parent_id,
        'parentAccessible': parent_accessible,
        'name': folder.name,
        'description': folder.description,
        'author': folder.author,
        'color': folder.color,
        'position': folder.position,
        'role': role_for_folder(folder),
        # Is there a share on this exact folder (not an ancestor, not
        # ownership)? That's what "Leave" in the UI revokes -- distinct from
        # role, which also reflects ownership or an inherited ancestor share.
        'directShare': ResourceShare.query.filter_by(folder_id=folder.id, user_id=current_user.id).first()
        is not None,
    }


def chapter_summary_dict(chapter: Chapter) -> dict:
    folder = db.session.get(Folder, chapter.folder_id)
    return {
        'id': chapter.id,
        'bookId': chapter.book_id,
        'folderId': chapter.folder_id,
        'folderAccessible': folder is not None and role_for_folder(folder) is not None,
        'name': chapter.name,
        'description': chapter.description,
        'position': chapter.position,
        'updatedAt': chapter.updated_at.isoformat(),
        'completedAt': chapter.completed_at.isoformat() if chapter.completed_at else None,
        'role': role_for_chapter(chapter),
        'directShare': ResourceShare.query.filter_by(chapter_id=chapter.id, user_id=current_user.id).first()
        is not None,
    }


def share_dict(share: ResourceShare) -> dict:
    return {'userId': share.user_id, 'username': share.user.username, 'role': share.role.value}


def chapter_detail_dict(chapter: Chapter) -> dict:
    d = chapter_summary_dict(chapter)
    d['contentHtml'] = chapter.content_html
    d['notesText'] = chapter.notes_text
    return d


def chapter_version_summary_dict(version: ChapterVersion) -> dict:
    text = html_to_text(version.content_html).strip()
    preview = text[:140] + ('…' if len(text) > 140 else '')
    return {
        'id': version.id,
        'createdAt': version.created_at.isoformat(),
        'wordCount': len(text.split()) if text else 0,
        'preview': preview,
    }


def resource_breadcrumb(folder: Folder | None = None, chapter: Chapter | None = None) -> list:
    """Ancestor folders from the book root down to (but not including) the
    resource itself -- empty for a book (no ancestors) or anything sitting
    directly in a book's root. Only the book entry carries a color, same
    isBook-gated convention as goal_resource_info/FolderTreeNode."""
    if chapter is not None:
        start = db.session.get(Folder, chapter.folder_id)
    elif folder is not None and folder.parent_id is not None:
        start = db.session.get(Folder, folder.parent_id)
    else:
        return []
    chain = []
    node = start
    while node is not None:
        chain.append(node)
        node = db.session.get(Folder, node.parent_id) if node.parent_id is not None else None
    chain.reverse()
    return [{'id': f.id, 'name': f.name, 'color': (f.color or None) if f.parent_id is None else None} for f in chain]


def goal_resource_info(goal: Goal) -> dict:
    if goal.folder_id is not None:
        folder = db.session.get(Folder, goal.folder_id)
        is_book = (folder.parent_id is None) if folder else None
        return {
            'resourceType': 'folder',
            'resourceId': goal.folder_id,
            'resourceName': folder.name if folder else None,
            'resourceIsBook': is_book,
            # Only a book itself carries a color in the UI (see
            # FolderTreeNode's isBook-gated color) -- a sub-folder's own
            # color column isn't otherwise shown anywhere, so it's left
            # unset here too rather than introducing a new usage of it.
            'resourceColor': (folder.color or None) if (folder and is_book) else None,
            'resourceBreadcrumb': resource_breadcrumb(folder=folder) if folder else [],
            'resourceAccessible': folder is not None and role_for_folder(folder) is not None,
        }
    chapter = db.session.get(Chapter, goal.chapter_id)
    return {
        'resourceType': 'chapter',
        'resourceId': goal.chapter_id,
        'resourceName': chapter.name if chapter else None,
        'resourceIsBook': None,
        'resourceColor': None,
        'resourceBreadcrumb': resource_breadcrumb(chapter=chapter) if chapter else [],
        'resourceAccessible': chapter is not None and role_for_chapter(chapter) is not None,
    }


def goal_progress(goal: Goal) -> dict:
    if goal.cadence is not None:
        period_end = advance_date_by_cadence(goal.period_start, goal.cadence.value) - datetime.timedelta(days=1)
        # A recurring goal's own end_date can fall mid-period (it isn't
        # necessarily a cadence boundary) -- report that as the true end
        # of the current (and final) period rather than the full period.
        if goal.end_date is not None and goal.end_date < period_end:
            period_end = goal.end_date
    else:
        period_end = goal.end_date
    if goal.goal_type == GoalType.words:
        current = (
            max(0, resource_word_count(folder=goal.folder, chapter=goal.chapter) - goal.baseline_word_count)
            if goal.baseline_word_count is not None
            else 0
        )
    else:
        current = resource_completed_chapter_count(goal.folder, goal.period_start)
    percent = min(100, round(current / goal.target * 100)) if goal.target > 0 else 0
    return {
        'current': current,
        'percent': percent,
        'periodStart': goal.period_start.isoformat(),
        'periodEnd': period_end.isoformat() if period_end else None,
        'achieved': current >= goal.target,
        'started': goal.goal_type != GoalType.words or goal.baseline_word_count is not None,
    }


def goal_dict(goal: Goal) -> dict:
    d = {
        'id': goal.id,
        'name': goal.name,
        'goalType': goal.goal_type.value,
        'target': goal.target,
        'cadence': goal.cadence.value if goal.cadence else None,
        'startDate': goal.start_date.isoformat(),
        'endDate': goal.end_date.isoformat() if goal.end_date else None,
        'createdAt': goal.created_at.isoformat(),
    }
    d.update(goal_resource_info(goal))
    d.update(goal_progress(goal))
    return d


def settings_to_dict(settings: UserSettings) -> dict:
    return {
        'darkMode': settings.dark_mode,
        'sidebarColor': settings.sidebar_color,
        'textColor': settings.text_color,
        'bgColor': settings.bg_color,
        'toolbarColor': settings.toolbar_color,
        'editorColor': settings.editor_color,
        'darkSidebarColor': settings.dark_sidebar_color,
        'darkTextColor': settings.dark_text_color,
        'darkBgColor': settings.dark_bg_color,
        'darkToolbarColor': settings.dark_toolbar_color,
        'darkEditorColor': settings.dark_editor_color,
        'openBookIds': settings.open_book_ids,
        'closedFolderIds': settings.closed_folder_ids,
        'closedChapterIds': settings.closed_chapter_ids,
        'bookOrder': settings.book_order,
        'hiddenGoalIds': settings.hidden_goal_ids,
        'goalOrder': settings.goal_order,
    }


# ---------------------------------------------------------------- auth --

@api_bp.route('/auth/login', methods=['POST'])
@csrf.exempt
def api_login():
    # No prior session exists before login, so there's no CSRF secret to check
    # against yet (unlike the Jinja UI, which always renders a token first).
    # The credentials themselves are the protection here; every other mutating
    # /api/* route still requires a valid X-CSRFToken header once authenticated.
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    password = data.get('password', '')
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return error('Incorrect username or password', 401)
    login_user(user)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'isAdmin': user.is_admin,
        'csrfToken': generate_csrf(),
        'version': VERSION,
    })


@api_bp.route('/auth/logout', methods=['POST'])
def api_logout():
    logout_user()
    return ('', 204)


@api_bp.route('/auth/me')
def api_me():
    if not current_user.is_authenticated:
        return error('Not authenticated', 401)
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'isAdmin': current_user.is_admin,
        'csrfToken': generate_csrf(),
        'version': VERSION,
    })


@api_bp.route('/me/password', methods=['PATCH'])
def api_change_password():
    data = request.get_json(silent=True) or {}
    current_password = data.get('currentPassword', '')
    new_password = data.get('newPassword', '')
    if not check_password_hash(current_user.password_hash, current_password):
        return error('Current password is incorrect', 401)
    if len(new_password) < 8:
        return error('New password must be at least 8 characters')
    current_user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return ('', 204)


# -------------------------------------------------------------- invites --

INVITE_EXPIRY = datetime.timedelta(days=7)


def _invite_or_error(token: str):
    """Shared validity check for the two public invite routes below. Returns
    (invite, None) if usable, or (None, error_response) otherwise."""
    invite = Invite.query.filter_by(token=token).first()
    if not invite:
        return None, error('Invalid invite link', 404)
    if invite.used_at is not None:
        return None, error('This invite link has already been used', 410)
    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
    if expires_at < datetime.datetime.now(datetime.timezone.utc):
        return None, error('This invite link has expired', 410)
    return invite, None


@api_bp.route('/invites', methods=['POST'])
def api_create_invite():
    if not current_user.is_admin:
        return error('Admin access required', 403)
    invite = Invite(
        token=secrets.token_urlsafe(32),
        created_by_id=current_user.id,
        expires_at=datetime.datetime.now(datetime.timezone.utc) + INVITE_EXPIRY,
    )
    db.session.add(invite)
    db.session.commit()
    return jsonify({'token': invite.token, 'expiresAt': invite.expires_at.isoformat()}), 201


@api_bp.route('/invites/<token>', methods=['GET'])
@csrf.exempt
def api_get_invite(token):
    # Public: a brand-new user hitting this link has no session/CSRF token yet.
    invite, err = _invite_or_error(token)
    if err:
        return err
    return jsonify({'expiresAt': invite.expires_at.isoformat()})


@api_bp.route('/invites/<token>/accept', methods=['POST'])
@csrf.exempt
def api_accept_invite(token):
    invite, err = _invite_or_error(token)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password', '')
    if not username:
        return error('Username is required')
    if len(username) > 80:
        return error('Username must be 80 characters or fewer')
    if len(password) < 8:
        return error('Password must be at least 8 characters')
    if User.query.filter_by(username=username).first():
        return error('That username is already taken', 409)

    user = User(username=username, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.flush()
    db.session.add(UserSettings(user_id=user.id))
    invite.used_at = datetime.datetime.now(datetime.timezone.utc)
    invite.used_by_id = user.id
    db.session.commit()

    login_user(user)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'isAdmin': user.is_admin,
        'csrfToken': generate_csrf(),
        'version': VERSION,
    })


@api_bp.route('/changelog')
def api_changelog():
    path = os.path.join(os.path.dirname(__file__), 'CHANGELOG.md')
    content = ''
    if os.path.isfile(path):
        with open(path) as f:
            content = f.read()
    return jsonify({'content': content})


# --------------------------------------------------------------- books --

@api_bp.route('/books')
def api_list_books():
    return jsonify([book_to_dict(b) for b in ordered_accessible_books()])


@api_bp.route('/stats')
def api_workspace_stats():
    """Same shape as the per-folder/per-chapter stats endpoints, aggregated
    across every book the current user has whole-book access to (their own
    plus ones shared with them) -- the workspace-wide view."""
    days = int(request.args.get('days', 7))
    book_ids = accessible_book_ids()
    chapters = Chapter.query.filter(Chapter.book_id.in_(book_ids)).all() if book_ids else []
    total_words = 0
    words_per_day = {}
    for chapter in chapters:
        count = len(html_to_text(chapter.content_html).split())
        total_words += count
        day = chapter.updated_at.date().isoformat()
        words_per_day[day] = words_per_day.get(day, 0) + count
    if days > 0:
        cutoff = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
        words_per_day = {d: c for d, c in words_per_day.items() if d >= cutoff}
    return jsonify({'totalWords': total_words, 'wordsPerDay': prune_words_per_day(words_per_day)})


@api_bp.route('/books', methods=['POST'])
def api_create_book():
    data = request.get_json(silent=True) or {}
    name = clean_name(data.get('name', ''))
    if not name:
        return error('name is required')
    if Folder.query.filter_by(parent_id=None, name=name).first():
        return error('Name already exists', 409)
    book = create_book(name, owner_id=current_user.id)
    settings = get_user_settings()
    settings.open_book_ids = settings.open_book_ids + [book.id]
    db.session.commit()
    return jsonify(book_to_dict(book)), 201


@api_bp.route('/books/<int:book_id>')
def api_get_book(book_id):
    book = require_book_access(book_id, 'viewer')
    return jsonify(book_to_dict(book))


@api_bp.route('/books/<int:book_id>', methods=['PATCH'])
def api_update_book(book_id):
    book = require_book_access(book_id, 'editor')
    data = request.get_json(silent=True) or {}
    if 'name' in data:
        new_name = clean_name(data['name'])
        if not new_name:
            return error('name cannot be empty')
        if new_name != book.name and Folder.query.filter_by(parent_id=None, name=new_name).first():
            return error('Name already exists', 409)
        book.name = new_name
    if 'description' in data:
        book.description = data['description']
    if 'author' in data:
        book.author = data['author']
    if 'color' in data:
        book.color = data['color']
    db.session.commit()
    return jsonify(book_to_dict(book))


@api_bp.route('/books/<int:book_id>', methods=['DELETE'])
def api_delete_book(book_id):
    book = require_book_access(book_id, 'owner')
    db.session.delete(book)
    db.session.commit()
    return ('', 204)


@api_bp.route('/books/wizard', methods=['POST'])
def api_create_book_wizard():
    data = request.get_json(silent=True) or {}
    title = clean_name(data.get('title', ''))
    chapters_name = clean_name(data.get('chapters', 'Chapters'))
    author_text = (data.get('author') or '').strip()
    color_value = (data.get('color') or '#dddddd').strip()
    extras = data.get('extras') or []
    if not title:
        return error('title is required')
    if Folder.query.filter_by(parent_id=None, name=title).first():
        return error('Name already exists', 409)
    book = create_book(title, owner_id=current_user.id, author=author_text, color=color_value)
    if chapters_name:
        chap_folder = Folder(parent_id=book.id, book_id=book.id, name=chapters_name, position=0)
        db.session.add(chap_folder)
        db.session.flush()
        db.session.add(Chapter(folder_id=chap_folder.id, book_id=book.id, name='Chapter One', position=0))
    for idx, sub in enumerate(extras, start=1):
        sub_name = clean_name(sub)
        if sub_name and not Folder.query.filter_by(parent_id=book.id, name=sub_name).first():
            db.session.add(Folder(parent_id=book.id, book_id=book.id, name=sub_name, position=idx))
    settings = get_user_settings()
    settings.open_book_ids = settings.open_book_ids + [book.id]
    db.session.commit()
    return jsonify(book_to_dict(book)), 201


@api_bp.route('/books/<int:book_id>/export.docx')
def api_export_book_docx(book_id):
    book = require_book_access(book_id, 'viewer')
    chapters = Chapter.query.filter_by(folder_id=book.id).order_by(Chapter.position, Chapter.created_at).all()
    doc = render_book_docx(chapters)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    parts = [book.name] + ([book.author] if book.author else [])
    filename = " - ".join(parts) + ".docx"
    return send_file(bio, as_attachment=True, download_name=filename,
                      mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


# ---------------------------------------------------------------- shares --
# Sharing a whole book is a share on its root folder row -- these folder
# endpoints work for both. Sub-folder and chapter shares grant access to
# just that item (and, for a folder, everything nested under it).

def _add_share(existing_query, make_share, book: Folder):
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    role = data.get('role', '')
    if role not in ('editor', 'viewer'):
        return None, error('role must be "editor" or "viewer"')
    user = User.query.filter_by(username=username).first()
    if not user:
        return None, error('No such user', 404)
    if user.id == book.owner_id:
        return None, error('User already owns this book', 409)
    share = existing_query(user.id).first()
    if share:
        share.role = ShareRole(role)
    else:
        share = make_share(user.id, ShareRole(role))
        db.session.add(share)
    db.session.commit()
    return share, None


@api_bp.route('/folders/<int:folder_id>/shares')
def api_list_folder_shares(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    require_folder_share_management(folder)
    rows = ResourceShare.query.filter_by(folder_id=folder_id).all()
    return jsonify([share_dict(r) for r in rows])


@api_bp.route('/folders/<int:folder_id>/shares', methods=['POST'])
def api_add_folder_share(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    require_folder_share_management(folder)
    book = db.session.get(Folder, folder.book_id)
    share, err = _add_share(
        lambda uid: ResourceShare.query.filter_by(folder_id=folder_id, user_id=uid),
        lambda uid, role: ResourceShare(folder_id=folder_id, user_id=uid, role=role),
        book,
    )
    if err:
        return err
    return jsonify(share_dict(share)), 201


@api_bp.route('/folders/<int:folder_id>/shares/<int:user_id>', methods=['PATCH'])
def api_update_folder_share(folder_id, user_id):
    folder = Folder.query.get_or_404(folder_id)
    require_folder_share_management(folder)
    data = request.get_json(silent=True) or {}
    role = data.get('role', '')
    if role not in ('editor', 'viewer'):
        return error('role must be "editor" or "viewer"')
    share = ResourceShare.query.filter_by(folder_id=folder_id, user_id=user_id).first()
    if not share:
        return error('Not shared with this user', 404)
    share.role = ShareRole(role)
    db.session.commit()
    return jsonify(share_dict(share))


@api_bp.route('/folders/<int:folder_id>/shares/<int:user_id>', methods=['DELETE'])
def api_remove_folder_share(folder_id, user_id):
    folder = Folder.query.get_or_404(folder_id)
    # A share can always be revoked by whoever manages it, or by the person
    # it was granted to (leaving on their own, no management role needed).
    if user_id != current_user.id:
        require_folder_share_management(folder)
    share = ResourceShare.query.filter_by(folder_id=folder_id, user_id=user_id).first()
    if not share:
        return error('Not shared with this user', 404)
    db.session.delete(share)
    db.session.commit()
    return ('', 204)


@api_bp.route('/chapters/<int:chapter_id>/shares')
def api_list_chapter_shares(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    require_chapter_share_management(chapter)
    rows = ResourceShare.query.filter_by(chapter_id=chapter_id).all()
    return jsonify([share_dict(r) for r in rows])


@api_bp.route('/chapters/<int:chapter_id>/shares', methods=['POST'])
def api_add_chapter_share(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    require_chapter_share_management(chapter)
    book = db.session.get(Folder, chapter.book_id)
    share, err = _add_share(
        lambda uid: ResourceShare.query.filter_by(chapter_id=chapter_id, user_id=uid),
        lambda uid, role: ResourceShare(chapter_id=chapter_id, user_id=uid, role=role),
        book,
    )
    if err:
        return err
    return jsonify(share_dict(share)), 201


@api_bp.route('/chapters/<int:chapter_id>/shares/<int:user_id>', methods=['PATCH'])
def api_update_chapter_share(chapter_id, user_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    require_chapter_share_management(chapter)
    data = request.get_json(silent=True) or {}
    role = data.get('role', '')
    if role not in ('editor', 'viewer'):
        return error('role must be "editor" or "viewer"')
    share = ResourceShare.query.filter_by(chapter_id=chapter_id, user_id=user_id).first()
    if not share:
        return error('Not shared with this user', 404)
    share.role = ShareRole(role)
    db.session.commit()
    return jsonify(share_dict(share))


@api_bp.route('/chapters/<int:chapter_id>/shares/<int:user_id>', methods=['DELETE'])
def api_remove_chapter_share(chapter_id, user_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    if user_id != current_user.id:
        require_chapter_share_management(chapter)
    share = ResourceShare.query.filter_by(chapter_id=chapter_id, user_id=user_id).first()
    if not share:
        return error('Not shared with this user', 404)
    db.session.delete(share)
    db.session.commit()
    return ('', 204)


@api_bp.route('/shared-with-me')
def api_shared_with_me():
    folders, chapters = shared_items()
    items = [
        {
            'type': 'folder',
            'id': f.id,
            'parentId': f.parent_id,
            'name': f.name,
            'role': role_for_folder(f),
            'bookName': db.session.get(Folder, f.book_id).name,
        }
        for f in folders
    ] + [
        {
            'type': 'chapter',
            'id': c.id,
            'parentId': None,
            'name': c.name,
            'role': role_for_chapter(c),
            'bookName': db.session.get(Folder, c.book_id).name,
        }
        for c in chapters
    ]
    items.sort(key=lambda i: i['name'].lower())
    return jsonify(items)


# ------------------------------------------------------------- folders --

@api_bp.route('/folders/<int:folder_id>')
def api_get_folder(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    subfolders = Folder.query.filter_by(parent_id=folder.id).order_by(Folder.position, Folder.created_at).all()
    chapters = Chapter.query.filter_by(folder_id=folder.id).order_by(Chapter.position, Chapter.created_at).all()
    d = folder_to_dict(folder)
    d['folders'] = [folder_to_dict(f) for f in subfolders]
    d['chapters'] = [chapter_summary_dict(c) for c in chapters]
    return jsonify(d)


@api_bp.route('/folders/<int:folder_id>/tree-ids')
def api_folder_tree_ids(folder_id):
    """Every sub-folder and chapter id nested under this folder (not
    including the folder itself) -- for "Open all", which un-hides a whole
    subtree from the sidebar in one action."""
    folder = require_folder_access(folder_id, 'viewer')
    folder_ids = [fid for fid in descendant_folder_ids(folder.id) if fid != folder.id]
    chapter_ids = [
        c.id
        for c in Chapter.query.filter(Chapter.folder_id.in_(descendant_folder_ids(folder.id))).with_entities(Chapter.id).all()
    ]
    return jsonify({'folderIds': folder_ids, 'chapterIds': chapter_ids})


@api_bp.route('/folders/<int:folder_id>/tree')
def api_folder_tree(folder_id):
    """Every sub-folder and chapter nested under this folder (not including
    the folder itself), flattened depth-first with a name and depth on each
    entry -- for a picker that needs to let someone choose any sub-folder or
    chapter within a book in one dropdown (see the goal-creation modal),
    where tree-ids' bare id lists aren't enough."""
    folder = require_folder_access(folder_id, 'viewer')
    entries = []

    def walk(parent_id, depth):
        subfolders = Folder.query.filter_by(parent_id=parent_id).order_by(Folder.position, Folder.created_at).all()
        for f in subfolders:
            entries.append({'id': f.id, 'type': 'folder', 'name': f.name, 'depth': depth})
            walk(f.id, depth + 1)
        chapters = Chapter.query.filter_by(folder_id=parent_id).order_by(Chapter.position, Chapter.created_at).all()
        for c in chapters:
            entries.append({'id': c.id, 'type': 'chapter', 'name': c.name, 'depth': depth})

    walk(folder.id, 0)
    return jsonify(entries)


@api_bp.route('/folders/<int:folder_id>/stats')
def api_folder_stats(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    days = int(request.args.get('days', 7))
    folder_ids = descendant_folder_ids(folder.id)
    chapters = Chapter.query.filter(Chapter.folder_id.in_(folder_ids)).all()
    total_words = 0
    words_per_day = {}
    for chapter in chapters:
        count = len(html_to_text(chapter.content_html).split())
        total_words += count
        day = chapter.updated_at.date().isoformat()
        words_per_day[day] = words_per_day.get(day, 0) + count
    if days > 0:
        cutoff = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
        words_per_day = {d: c for d, c in words_per_day.items() if d >= cutoff}
    return jsonify({'totalWords': total_words, 'wordsPerDay': prune_words_per_day(words_per_day)})


@api_bp.route('/folders', methods=['POST'])
def api_create_folder():
    data = request.get_json(silent=True) or {}
    parent_id = data.get('parentId')
    name = clean_name(data.get('name', ''))
    if not parent_id or not name:
        return error('parentId and name are required')
    parent = require_folder_access(parent_id, 'editor')
    if Folder.query.filter_by(parent_id=parent.id, name=name).first():
        return error('Name already exists', 409)
    folder = Folder(
        parent_id=parent.id,
        book_id=parent.book_id,
        name=name,
        description=data.get('description', ''),
        position=next_folder_position(parent.id),
    )
    db.session.add(folder)
    db.session.commit()
    return jsonify(folder_to_dict(folder)), 201


@api_bp.route('/folders/<int:folder_id>', methods=['PATCH'])
def api_update_folder(folder_id):
    folder = require_folder_access(folder_id, 'editor')
    data = request.get_json(silent=True) or {}
    if 'name' in data:
        new_name = clean_name(data['name'])
        if not new_name:
            return error('name cannot be empty')
        if new_name != folder.name and Folder.query.filter_by(parent_id=folder.parent_id, name=new_name).first():
            return error('Name already exists', 409)
        folder.name = new_name
    if 'description' in data:
        folder.description = data['description']
    if 'author' in data:
        folder.author = data['author']
    db.session.commit()
    return jsonify(folder_to_dict(folder))


@api_bp.route('/folders/<int:folder_id>', methods=['DELETE'])
def api_delete_folder(folder_id):
    folder = require_folder_access(folder_id, 'editor')
    db.session.delete(folder)
    db.session.commit()
    return ('', 204)


@api_bp.route('/folders/<int:folder_id>/export.docx')
def api_export_folder_docx(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    book = db.session.get(Folder, folder.book_id)
    chapters = folder_chapters_recursive(folder_id)
    doc = render_folder_docx(folder.name, chapters)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=export_filename(book, folder.name, 'docx'),
                      mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


@api_bp.route('/folders/<int:folder_id>/export.rtf')
def api_export_folder_rtf(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    book = db.session.get(Folder, folder.book_id)
    chapters = folder_chapters_recursive(folder_id)
    bio = BytesIO(render_folder_rtf(folder.name, chapters))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, folder.name, 'rtf'),
                      mimetype='application/rtf')


@api_bp.route('/folders/<int:folder_id>/export.txt')
def api_export_folder_txt(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    book = db.session.get(Folder, folder.book_id)
    chapters = folder_chapters_recursive(folder_id)
    bio = BytesIO(render_folder_txt(folder.name, chapters).encode('utf-8'))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, folder.name, 'txt'),
                      mimetype='text/plain')


@api_bp.route('/folders/<int:folder_id>/export.md')
def api_export_folder_md(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    book = db.session.get(Folder, folder.book_id)
    chapters = folder_chapters_recursive(folder_id)
    bio = BytesIO(render_folder_markdown(folder.name, chapters).encode('utf-8'))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, folder.name, 'md'),
                      mimetype='text/markdown')


@api_bp.route('/folders/<int:folder_id>/reorder', methods=['POST'])
def api_reorder_folder(folder_id):
    folder = require_folder_access(folder_id, 'editor')
    data = request.get_json(silent=True) or {}
    typ = data.get('type')
    ids_order = data.get('order', [])
    if typ == 'folder':
        children = Folder.query.filter_by(parent_id=folder.id).all()
    elif typ == 'chapter':
        children = Chapter.query.filter_by(folder_id=folder.id).all()
    else:
        return error('type must be "folder" or "chapter"')
    by_id = {c.id: c for c in children}
    for idx, cid in enumerate(ids_order):
        obj = by_id.pop(cid, None)
        if obj is not None:
            obj.position = idx
    remaining = sorted(by_id.values(), key=lambda c: c.position)
    for i, obj in enumerate(remaining, start=len(ids_order)):
        obj.position = i
    db.session.commit()
    return ('', 204)


# ------------------------------------------------------------ chapters --

@api_bp.route('/chapters', methods=['POST'])
def api_create_chapter():
    data = request.get_json(silent=True) or {}
    folder_id = data.get('folderId')
    name = clean_name(data.get('name', ''))
    if not folder_id or not name:
        return error('folderId and name are required')
    folder = require_folder_access(folder_id, 'editor')
    if Chapter.query.filter_by(folder_id=folder.id, name=name).first():
        return error('Name already exists', 409)
    chapter = Chapter(
        folder_id=folder.id,
        book_id=folder.book_id,
        name=name,
        description=data.get('description', ''),
        position=next_chapter_position(folder.id),
    )
    db.session.add(chapter)
    db.session.commit()
    return jsonify(chapter_detail_dict(chapter)), 201


@api_bp.route('/chapters/<int:chapter_id>')
def api_get_chapter(chapter_id):
    chapter = require_chapter_access(chapter_id, 'viewer')
    return jsonify(chapter_detail_dict(chapter))


@api_bp.route('/chapters/<int:chapter_id>', methods=['PATCH'])
def api_update_chapter(chapter_id):
    chapter = require_chapter_access(chapter_id, 'editor')
    data = request.get_json(silent=True) or {}
    if 'expectedUpdatedAt' in data and not _matches_updated_at(chapter, data['expectedUpdatedAt']):
        return error('This chapter was changed elsewhere. Reload to see the latest version.', 409)
    if 'name' in data:
        new_name = clean_name(data['name'])
        if not new_name:
            return error('name cannot be empty')
        if new_name != chapter.name and Chapter.query.filter_by(folder_id=chapter.folder_id, name=new_name).first():
            return error('Name already exists', 409)
        chapter.name = new_name
    if 'description' in data:
        chapter.description = data['description']
    if 'folderId' in data:
        new_folder = require_folder_access(data['folderId'], 'editor')
        if new_folder.id != chapter.folder_id:
            if Chapter.query.filter_by(folder_id=new_folder.id, name=chapter.name).first():
                return error('Name already exists in destination folder', 409)
            chapter.folder_id = new_folder.id
            chapter.book_id = new_folder.book_id
            chapter.position = next_chapter_position(new_folder.id)
    if 'contentHtml' in data:
        new_content = sanitize_html(data['contentHtml'])
        if new_content != chapter.content_html:
            snapshot_chapter_version(chapter)
            chapter.content_html = new_content
    if 'notesText' in data:
        chapter.notes_text = data['notesText']
    if 'completed' in data:
        if data['completed']:
            if chapter.completed_at is None:
                chapter.completed_at = datetime.datetime.now(datetime.timezone.utc)
        else:
            chapter.completed_at = None
    db.session.commit()
    return jsonify(chapter_detail_dict(chapter))


@api_bp.route('/chapters/<int:chapter_id>', methods=['DELETE'])
def api_delete_chapter(chapter_id):
    chapter = require_chapter_access(chapter_id, 'editor')
    db.session.delete(chapter)
    db.session.commit()
    return ('', 204)


@api_bp.route('/chapters/<int:chapter_id>/export.docx')
def api_export_chapter_docx(chapter_id):
    chapter = require_chapter_access(chapter_id, 'viewer')
    doc = render_chapter_docx(chapter.content_html)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    book = db.session.get(Folder, chapter.book_id)
    filename = export_filename(book, chapter.name, 'docx')
    return send_file(bio, as_attachment=True, download_name=filename,
                      mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


@api_bp.route('/chapters/<int:chapter_id>/export.rtf')
def api_export_chapter_rtf(chapter_id):
    chapter = require_chapter_access(chapter_id, 'viewer')
    book = db.session.get(Folder, chapter.book_id)
    bio = BytesIO(render_chapter_rtf(chapter.content_html))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, chapter.name, 'rtf'),
                      mimetype='application/rtf')


@api_bp.route('/chapters/<int:chapter_id>/export.txt')
def api_export_chapter_txt(chapter_id):
    chapter = require_chapter_access(chapter_id, 'viewer')
    book = db.session.get(Folder, chapter.book_id)
    bio = BytesIO(html_to_text(chapter.content_html).encode('utf-8'))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, chapter.name, 'txt'),
                      mimetype='text/plain')


@api_bp.route('/chapters/<int:chapter_id>/export.md')
def api_export_chapter_md(chapter_id):
    chapter = require_chapter_access(chapter_id, 'viewer')
    book = db.session.get(Folder, chapter.book_id)
    bio = BytesIO(html_to_markdown(chapter.content_html).encode('utf-8'))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, chapter.name, 'md'),
                      mimetype='text/markdown')


@api_bp.route('/chapters/<int:chapter_id>/versions')
def api_list_chapter_versions(chapter_id):
    require_chapter_access(chapter_id, 'viewer')
    versions = (
        ChapterVersion.query.filter_by(chapter_id=chapter_id)
        .order_by(ChapterVersion.created_at.desc())
        .all()
    )
    return jsonify([chapter_version_summary_dict(v) for v in versions])


@api_bp.route('/chapters/<int:chapter_id>/versions/<int:version_id>')
def api_get_chapter_version(chapter_id, version_id):
    require_chapter_access(chapter_id, 'viewer')
    version = ChapterVersion.query.filter_by(id=version_id, chapter_id=chapter_id).first_or_404()
    d = chapter_version_summary_dict(version)
    d['contentHtml'] = version.content_html
    return jsonify(d)


@api_bp.route('/chapters/<int:chapter_id>/versions/<int:version_id>/restore', methods=['POST'])
def api_restore_chapter_version(chapter_id, version_id):
    chapter = require_chapter_access(chapter_id, 'editor')
    version = ChapterVersion.query.filter_by(id=version_id, chapter_id=chapter_id).first_or_404()
    if version.content_html != chapter.content_html:
        # Force this checkpoint regardless of the 5-minute gate, so restoring
        # is itself always recoverable through history too.
        snapshot_chapter_version(chapter, force=True)
        chapter.content_html = version.content_html
    db.session.commit()
    return jsonify(chapter_detail_dict(chapter))


@api_bp.route('/chapters/<int:chapter_id>/stats')
def api_chapter_stats(chapter_id):
    """Word count over time for a single chapter, from its version
    checkpoints (unlike folder/book stats, which bucket by each chapter's
    last-edited day -- a single chapter's own history is available, so this
    charts real word-count-per-day instead of that coarser proxy)."""
    chapter = require_chapter_access(chapter_id, 'viewer')
    days = int(request.args.get('days', 7))
    words_per_day = {}
    versions = ChapterVersion.query.filter_by(chapter_id=chapter.id).order_by(ChapterVersion.created_at).all()
    for version in versions:
        day = version.created_at.date().isoformat()
        words_per_day[day] = len(html_to_text(version.content_html).split())
    total_words = len(html_to_text(chapter.content_html).split())
    words_per_day[datetime.date.today().isoformat()] = total_words
    if days > 0:
        cutoff = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
        words_per_day = {d: c for d, c in words_per_day.items() if d >= cutoff}
    return jsonify({'totalWords': total_words, 'wordsPerDay': prune_words_per_day(words_per_day)})


PRESENCE_RECENT_WINDOW = datetime.timedelta(seconds=30)


@api_bp.route('/chapters/<int:chapter_id>/presence', methods=['POST'])
def api_heartbeat_chapter_presence(chapter_id):
    require_chapter_access(chapter_id, 'viewer')
    row = ChapterPresence.query.filter_by(chapter_id=chapter_id, user_id=current_user.id).first()
    if row is None:
        row = ChapterPresence(chapter_id=chapter_id, user_id=current_user.id)
        db.session.add(row)
    else:
        row.last_seen = datetime.datetime.now(datetime.timezone.utc)
    db.session.commit()
    return ('', 204)


@api_bp.route('/chapters/<int:chapter_id>/presence')
def api_list_chapter_presence(chapter_id):
    require_chapter_access(chapter_id, 'viewer')
    cutoff = datetime.datetime.now(datetime.timezone.utc) - PRESENCE_RECENT_WINDOW
    rows = (
        ChapterPresence.query.filter(
            ChapterPresence.chapter_id == chapter_id,
            ChapterPresence.user_id != current_user.id,
            ChapterPresence.last_seen >= cutoff,
        ).all()
    )
    return jsonify([{'userId': r.user_id, 'username': r.user.username} for r in rows])


# --------------------------------------------------------------- goals --

@api_bp.route('/goals')
def api_list_goals():
    goals = Goal.query.filter_by(user_id=current_user.id).order_by(Goal.created_at.desc()).all()
    for goal in goals:
        advance_goal_period(goal)
    db.session.commit()
    return jsonify([goal_dict(g) for g in goals])


@api_bp.route('/goals', methods=['POST'])
def api_create_goal():
    data = request.get_json(silent=True) or {}
    resource_type = data.get('resourceType')
    resource_id = data.get('resourceId')
    goal_type = data.get('goalType')
    target = data.get('target')
    cadence = data.get('cadence')
    start_date_raw = data.get('startDate')
    end_date_raw = data.get('endDate')
    name = clean_name(data.get('name') or '')

    if resource_type not in ('folder', 'chapter'):
        return error('resourceType must be "folder" or "chapter"')
    if goal_type not in ('words', 'chapters'):
        return error('goalType must be "words" or "chapters"')
    if goal_type == 'chapters' and resource_type != 'folder':
        return error('Chapter-count goals can only be set on a book or sub-folder')
    if not isinstance(target, int) or isinstance(target, bool) or target <= 0:
        return error('target must be a positive integer')

    if resource_type == 'folder':
        folder = require_folder_access(resource_id, 'editor')
        folder_id, chapter_id = folder.id, None
    else:
        chapter = require_chapter_access(resource_id, 'editor')
        folder_id, chapter_id = None, chapter.id

    try:
        start_date = datetime.date.fromisoformat(start_date_raw) if start_date_raw else datetime.date.today()
    except (TypeError, ValueError):
        return error('startDate must be an ISO date')

    end_date = None
    if cadence is not None:
        if cadence not in ('daily', 'weekly', 'monthly'):
            return error('cadence must be "daily", "weekly", or "monthly"')
        # Optional for a recurring goal -- open-ended (never stops
        # recurring) unless a date is given, unlike a fixed-range goal
        # below, which always needs one.
        if end_date_raw:
            try:
                end_date = datetime.date.fromisoformat(end_date_raw)
            except (TypeError, ValueError):
                return error('endDate must be an ISO date')
            if end_date < start_date:
                return error('endDate must be on or after startDate')
    else:
        if not end_date_raw:
            return error('endDate is required for a fixed-range goal')
        try:
            end_date = datetime.date.fromisoformat(end_date_raw)
        except (TypeError, ValueError):
            return error('endDate must be an ISO date')
        if end_date < start_date:
            return error('endDate must be on or after startDate')

    goal = Goal(
        user_id=current_user.id,
        folder_id=folder_id,
        chapter_id=chapter_id,
        name=name,
        goal_type=GoalType(goal_type),
        target=target,
        cadence=GoalCadence(cadence) if cadence else None,
        start_date=start_date,
        end_date=end_date,
        period_start=start_date,
    )
    db.session.add(goal)
    db.session.flush()
    advance_goal_period(goal)
    db.session.commit()
    return jsonify(goal_dict(goal)), 201


@api_bp.route('/goals/<int:goal_id>', methods=['PATCH'])
def api_update_goal(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}

    if 'name' in data:
        goal.name = clean_name(data['name'] or '')

    if 'target' in data:
        if not isinstance(data['target'], int) or isinstance(data['target'], bool) or data['target'] <= 0:
            return error('target must be a positive integer')
        goal.target = data['target']

    new_start_date = None
    if 'startDate' in data:
        try:
            new_start_date = datetime.date.fromisoformat(data['startDate'])
        except (TypeError, ValueError):
            return error('startDate must be an ISO date')

    end_date_provided = 'endDate' in data
    new_end_date = None
    if end_date_provided and data['endDate']:
        try:
            new_end_date = datetime.date.fromisoformat(data['endDate'])
        except (TypeError, ValueError):
            return error('endDate must be an ISO date')
    elif end_date_provided and goal.cadence is None:
        # A fixed-range goal always has an end date -- only a recurring
        # goal can clear it back to "never ends" by sending endDate: ''.
        return error('A fixed-range goal must have an endDate')

    if new_start_date is not None or end_date_provided:
        effective_start = new_start_date if new_start_date is not None else goal.start_date
        effective_end = new_end_date if end_date_provided else goal.end_date
        if effective_end is not None and effective_end < effective_start:
            return error('endDate must be on or after startDate')
        if new_start_date is not None:
            # Moving the anchor date invalidates any baseline captured
            # against the old one -- re-anchor the current period here and
            # let advance_goal_period() lazily recapture it below (or roll
            # straight past it, if the new date is already in the past).
            goal.start_date = new_start_date
            goal.period_start = new_start_date
            goal.baseline_word_count = None
        if end_date_provided:
            goal.end_date = new_end_date

    advance_goal_period(goal)
    db.session.commit()
    return jsonify(goal_dict(goal))


@api_bp.route('/goals/<int:goal_id>', methods=['DELETE'])
def api_delete_goal(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    db.session.delete(goal)
    db.session.commit()
    return ('', 204)


def goal_period_history_dict(entry: GoalPeriodHistory) -> dict:
    return {
        'id': entry.id,
        'periodStart': entry.period_start.isoformat(),
        'periodEnd': entry.period_end.isoformat(),
        'target': entry.target,
        'current': entry.current,
        'percent': min(100, round(entry.current / entry.target * 100)) if entry.target > 0 else 0,
        'achieved': entry.achieved,
    }


@api_bp.route('/goals/<int:goal_id>/history')
def api_goal_history(goal_id):
    """Past completed periods of a recurring goal (see GoalPeriodHistory --
    only ever populated going forward from whenever the goal started being
    read after this feature shipped, not backfilled). Also rolls the goal
    itself forward first, so a period that just elapsed shows up
    immediately rather than waiting for some other request to trigger it."""
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    advance_goal_period(goal)
    db.session.commit()
    entries = (
        GoalPeriodHistory.query.filter_by(goal_id=goal.id)
        .order_by(GoalPeriodHistory.period_start.desc())
        .all()
    )
    return jsonify({'goal': goal_dict(goal), 'periods': [goal_period_history_dict(e) for e in entries]})


# ----------------------------------------------------------------- me --

@api_bp.route('/me/settings')
def api_get_settings():
    return jsonify(settings_to_dict(get_user_settings()))


@api_bp.route('/me/settings', methods=['PATCH'])
def api_update_settings():
    settings = get_user_settings()
    data = request.get_json(silent=True) or {}
    field_map = {
        'darkMode': 'dark_mode',
        'sidebarColor': 'sidebar_color',
        'textColor': 'text_color',
        'bgColor': 'bg_color',
        'toolbarColor': 'toolbar_color',
        'editorColor': 'editor_color',
        'darkSidebarColor': 'dark_sidebar_color',
        'darkTextColor': 'dark_text_color',
        'darkBgColor': 'dark_bg_color',
        'darkToolbarColor': 'dark_toolbar_color',
        'darkEditorColor': 'dark_editor_color',
        'openBookIds': 'open_book_ids',
        'closedFolderIds': 'closed_folder_ids',
        'closedChapterIds': 'closed_chapter_ids',
        'bookOrder': 'book_order',
        'hiddenGoalIds': 'hidden_goal_ids',
        'goalOrder': 'goal_order',
    }
    for api_key, attr in field_map.items():
        if api_key in data:
            setattr(settings, attr, data[api_key])
    db.session.commit()
    return jsonify(settings_to_dict(settings))


# -------------------------------------------------------------- search --

@api_bp.route('/search')
def api_search():
    query = (request.args.get('q') or '').strip()
    results = []
    if query:
        book_ids = accessible_book_ids()
        shared_folders, shared_chapters = shared_items()
        folder_ids = set()
        for f in shared_folders:
            folder_ids.update(descendant_folder_ids(f.id))
        chapter_ids = {c.id for c in shared_chapters}

        conditions = []
        if book_ids:
            conditions.append(Chapter.book_id.in_(book_ids))
        if folder_ids:
            conditions.append(Chapter.folder_id.in_(folder_ids))
        if chapter_ids:
            conditions.append(Chapter.id.in_(chapter_ids))

        candidates = []
        if conditions:
            candidates = (
                Chapter.query.filter(db.or_(*conditions))
                .filter(Chapter.search_tsv.match(query, postgresql_regconfig='english'))
                .all()
            )
        qlower = query.lower()
        for chapter in candidates:
            if qlower in chapter.name.lower() or qlower in html_to_text(chapter.content_html).lower():
                results.append({**chapter_summary_dict(chapter), 'matchType': 'chapter'})
            if qlower in (chapter.notes_text or '').lower():
                results.append({**chapter_summary_dict(chapter), 'matchType': 'notes'})
    return jsonify(results)


# ---------------------------------------------------------- export/import --

@api_bp.route('/export')
def api_export():
    mem = export_books_zip()
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    return send_file(mem, as_attachment=True, download_name=f"calwriter - {timestamp}.calwdb",
                      mimetype='application/x-calwriter-db')


@api_bp.route('/import', methods=['POST'])
def api_import():
    file = request.files.get('file')
    if not file or not file.filename.endswith('.calwdb'):
        return error('Invalid file')
    try:
        count = import_books_zip(file, owner_id=current_user.id)
    except ValueError as e:
        return error(str(e))
    return jsonify({'imported': count})
