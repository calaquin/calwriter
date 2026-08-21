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
from models import User, UserSettings, Folder, Chapter, ChapterVersion, ChapterPresence, BookCollaborator, BookRole, Invite
from permissions import (
    accessible_book_ids,
    require_book_access,
    require_folder_access,
    require_chapter_access,
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
    export_books_zip,
    import_books_zip,
    snapshot_chapter_version,
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


def role_for_book(book: Folder) -> str:
    if book.owner_id == current_user.id:
        return 'owner'
    collab = BookCollaborator.query.filter_by(book_id=book.id, user_id=current_user.id).first()
    return collab.role.value if collab else 'viewer'


def book_to_dict(book: Folder) -> dict:
    return {
        'id': book.id,
        'name': book.name,
        'description': book.description,
        'author': book.author,
        'color': book.color,
        'role': role_for_book(book),
        'createdAt': book.created_at.isoformat(),
        'updatedAt': book.updated_at.isoformat(),
    }


def folder_to_dict(folder: Folder) -> dict:
    return {
        'id': folder.id,
        'bookId': folder.book_id,
        'parentId': folder.parent_id,
        'name': folder.name,
        'description': folder.description,
        'author': folder.author,
        'color': folder.color,
        'position': folder.position,
    }


def chapter_summary_dict(chapter: Chapter) -> dict:
    return {
        'id': chapter.id,
        'bookId': chapter.book_id,
        'folderId': chapter.folder_id,
        'name': chapter.name,
        'description': chapter.description,
        'position': chapter.position,
        'updatedAt': chapter.updated_at.isoformat(),
    }


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


@api_bp.route('/books/<int:book_id>/stats')
def api_book_stats(book_id):
    require_book_access(book_id, 'viewer')
    days = int(request.args.get('days', 7))
    folder_ids = descendant_folder_ids(book_id)
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
    return jsonify({'totalWords': total_words, 'wordsPerDay': words_per_day})


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


# ---------------------------------------------------------- collaborators --

@api_bp.route('/books/<int:book_id>/collaborators')
def api_list_collaborators(book_id):
    require_book_access(book_id, 'owner')
    rows = BookCollaborator.query.filter_by(book_id=book_id).all()
    return jsonify([
        {'userId': r.user_id, 'username': r.user.username, 'role': r.role.value}
        for r in rows
    ])


@api_bp.route('/books/<int:book_id>/collaborators', methods=['POST'])
def api_add_collaborator(book_id):
    book = require_book_access(book_id, 'owner')
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    role = data.get('role', '')
    if role not in ('editor', 'viewer'):
        return error('role must be "editor" or "viewer"')
    user = User.query.filter_by(username=username).first()
    if not user:
        return error('No such user', 404)
    if user.id == book.owner_id:
        return error('User already owns this book', 409)
    collab = BookCollaborator.query.filter_by(book_id=book_id, user_id=user.id).first()
    if collab:
        collab.role = BookRole(role)
    else:
        collab = BookCollaborator(book_id=book_id, user_id=user.id, role=BookRole(role))
        db.session.add(collab)
    db.session.commit()
    return jsonify({'userId': user.id, 'username': user.username, 'role': role}), 201


@api_bp.route('/books/<int:book_id>/collaborators/<int:user_id>', methods=['PATCH'])
def api_update_collaborator(book_id, user_id):
    require_book_access(book_id, 'owner')
    data = request.get_json(silent=True) or {}
    role = data.get('role', '')
    if role not in ('editor', 'viewer'):
        return error('role must be "editor" or "viewer"')
    collab = BookCollaborator.query.filter_by(book_id=book_id, user_id=user_id).first()
    if not collab:
        return error('Not a collaborator', 404)
    collab.role = BookRole(role)
    db.session.commit()
    return jsonify({'userId': user_id, 'role': role})


@api_bp.route('/books/<int:book_id>/collaborators/<int:user_id>', methods=['DELETE'])
def api_remove_collaborator(book_id, user_id):
    require_book_access(book_id, 'owner')
    collab = BookCollaborator.query.filter_by(book_id=book_id, user_id=user_id).first()
    if not collab:
        return error('Not a collaborator', 404)
    db.session.delete(collab)
    db.session.commit()
    return ('', 204)


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
        ids = accessible_book_ids()
        if ids:
            candidates = (
                Chapter.query.filter(Chapter.book_id.in_(ids))
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
