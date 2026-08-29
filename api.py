"""JSON API backing the React frontend (frontend/). Addressed by id, not
name-path -- this is what lets routing avoid any path-traversal concerns."""
import datetime
import os
import secrets
import uuid
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user, login_user, logout_user
from flask_wtf.csrf import generate_csrf
from sqlalchemy.dialects.postgresql import insert as pg_insert
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, csrf
from models import (
    User,
    UserSettings,
    Folder,
    Chapter,
    ChapterVersion,
    ChapterPresence,
    ChapterWritingActivity,
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
    descendant_chapter_ids,
    chapter_ids_under_folder,
    chapter_ids_with_children,
    nearest_folder_for_chapter,
    lock_books_for_hierarchy_change,
    validate_folder_parent,
    validate_chapter_parent,
    HierarchyError,
    MAX_FOLDER_DEPTH,
    MAX_CHAPTER_DEPTH,
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
    resource_typed_words,
    resource_completed_chapter_count,
    advance_date_by_cadence,
    record_writing_activity,
    compute_writing_streak,
    chapter_last_activity_date,
    MAX_HEARTBEAT_ELAPSED,
    STALE_CHAPTER_DAYS,
    is_valid_timezone,
    user_local_datetime,
    user_local_today,
    writing_activity_totals,
    writing_activity_contributions,
    calculate_wpm,
    search_chapter_matches,
    build_search_snippet,
    BOOK_TYPES,
    journal_write_today,
    JOURNAL_DATE_FORMATS,
    JOURNAL_TIME_FORMATS,
    DEFAULT_JOURNAL_TIME_FORMAT,
    format_journal_time,
)

api_bp = Blueprint('api', __name__, url_prefix='/api')


def error(message, status=400):
    return jsonify({'error': message}), status


@api_bp.errorhandler(HierarchyError)
def handle_hierarchy_error(exc):
    """Every hierarchy-mutating endpoint (create/move for both chapters and
    folders) raises HierarchyError for a depth/cycle/cross-book violation --
    caught once here instead of each endpoint wrapping its own try/except."""
    return error(str(exc), 400)


def parse_uuid(value) -> uuid.UUID | None:
    """Parses an id supplied in a JSON request body (unlike a path segment,
    never validated by a route converter). Returns None on anything that
    isn't a well-formed UUID string, for the caller to turn into a clean 400."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def me_to_dict(user: User) -> dict:
    return {
        'id': user.id,
        'username': user.username,
        'isAdmin': user.is_admin,
        'timezone': user.timezone,
        'csrfToken': generate_csrf(),
        'version': VERSION,
    }


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
        'showBookColor': book.show_book_color,
        # P1.2. A pre-migration/never-set root row would read None here --
        # application logic (never a NOT NULL constraint, since Folder rows
        # of every kind share this column) treats that the same as
        # 'general' everywhere it matters; the migration itself already
        # backfills every existing Book, so this is a defensive fallback,
        # not the normal path.
        'bookType': book.book_type or 'general',
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
        'showBookColor': folder.show_book_color,
        'position': folder.position,
        'role': role_for_folder(folder),
        # Is there a share on this exact folder (not an ancestor, not
        # ownership)? That's what "Leave" in the UI revokes -- distinct from
        # role, which also reflects ownership or an inherited ancestor share.
        'directShare': ResourceShare.query.filter_by(folder_id=folder.id, user_id=current_user.id).first()
        is not None,
    }


def chapter_summary_dict(chapter: Chapter, *, has_children: bool | None = None) -> dict:
    """`has_children` lets a list endpoint pass in a pre-computed batched
    result (see services.chapter_ids_with_children) instead of this doing
    its own existence-check query per chapter -- pass it whenever calling
    this in a loop. Falls back to a single-chapter query when omitted
    (single-resource callers like chapter_detail_dict)."""
    if chapter.folder_id is not None:
        folder = db.session.get(Folder, chapter.folder_id)
        folder_accessible = folder is not None and role_for_folder(folder) is not None
        parent_chapter_id = None
        parent_chapter_accessible = False
    else:
        parent_chapter = db.session.get(Chapter, chapter.parent_chapter_id)
        folder_accessible = False
        parent_chapter_id = chapter.parent_chapter_id
        parent_chapter_accessible = parent_chapter is not None and role_for_chapter(parent_chapter) is not None
    return {
        'id': chapter.id,
        'bookId': chapter.book_id,
        'folderId': chapter.folder_id,
        'folderAccessible': folder_accessible,
        'parentChapterId': parent_chapter_id,
        'parentChapterAccessible': parent_chapter_accessible,
        'name': chapter.name,
        'description': chapter.description,
        'position': chapter.position,
        'updatedAt': chapter.updated_at.isoformat(),
        'completedAt': chapter.completed_at.isoformat() if chapter.completed_at else None,
        'showBookColor': chapter.show_book_color,
        # P1.2: the Journal day this chapter represents, if any -- see
        # Chapter.journal_date's docstring. Independent of name/Book Type.
        'journalDate': chapter.journal_date.isoformat() if chapter.journal_date else None,
        'role': role_for_chapter(chapter),
        'directShare': ResourceShare.query.filter_by(chapter_id=chapter.id, user_id=current_user.id).first()
        is not None,
        'hasChildren': (
            has_children if has_children is not None
            else Chapter.query.filter_by(parent_chapter_id=chapter.id).first() is not None
        ),
    }


def chapter_effective_book_color(chapter: Chapter) -> str | None:
    """The color the chapter's editor should tint its background with, or
    None if it shouldn't be tinted at all. Requires the chapter's own
    show_book_color AND every ancestor folder's AND the book root's to all
    be true -- any single level along the chain can opt the chapter out.
    nearest_folder_for_chapter resolves a nested chapter's containing
    Folder first (its own folder_id is NULL), then this walks that
    Folder's own ancestor chain exactly as before."""
    if not chapter.show_book_color:
        return None
    node = nearest_folder_for_chapter(chapter)
    while node is not None:
        if not node.show_book_color:
            return None
        if node.parent_id is None:
            return node.color or None
        node = db.session.get(Folder, node.parent_id)
    return None


def share_dict(share: ResourceShare) -> dict:
    return {'userId': share.user_id, 'username': share.user.username, 'role': share.role.value}


def chapter_detail_dict(chapter: Chapter) -> dict:
    d = chapter_summary_dict(chapter)
    d['contentHtml'] = chapter.content_html
    d['notesText'] = chapter.notes_text
    d['bookColor'] = chapter_effective_book_color(chapter)
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


def internal_reference_resolution(target_type: str, target_id: uuid.UUID) -> dict | None:
    """Resolve a typed UUID only when the current user can read its target.

    Returning None for both a missing row and an inaccessible row is
    deliberate: callers must not be able to use references to probe private
    workspace structure. Book and folder are both Folder rows, so the parent
    shape check also prevents a mismatched type from resolving accidentally.
    """
    if target_type == 'book':
        target = db.session.get(Folder, target_id)
        if target is None or target.parent_id is not None or role_for_folder(target) is None:
            return None
        route = f'/folders/{target.id}'
    elif target_type == 'folder':
        target = db.session.get(Folder, target_id)
        if target is None or target.parent_id is None or role_for_folder(target) is None:
            return None
        route = f'/folders/{target.id}'
    elif target_type == 'chapter':
        target = db.session.get(Chapter, target_id)
        if target is None or role_for_chapter(target) is None:
            return None
        route = f'/chapters/{target.id}'
    else:
        return None
    return {
        'targetType': target_type,
        'targetId': target.id,
        'name': target.name,
        'route': route,
    }


def internal_reference_picker_items() -> list[dict]:
    """All Book/Folder/Chapter targets readable by the current user.

    Whole-book access is walked from the root. Narrow direct shares surface
    as additional depth-zero roots only when their immediate parent is not
    readable; descendants inherit that access and are walked normally. This
    preserves a useful tree without exposing names of inaccessible ancestors.
    """
    items = []
    seen_folders = set()
    seen_chapters = set()

    def add_item(target_type, target, depth):
        book = db.session.get(Folder, target.book_id)
        items.append({
            'targetType': target_type,
            'targetId': target.id,
            'name': target.name,
            'depth': depth,
            # Shared-with-me already exposes this containing-book label for a
            # narrow share; it is context, not proof the book itself is readable.
            'bookName': book.name if book is not None else '',
        })

    def walk_chapter(chapter, depth):
        if chapter.id in seen_chapters:
            return
        seen_chapters.add(chapter.id)
        add_item('chapter', chapter, depth)
        children = (
            Chapter.query.filter_by(parent_chapter_id=chapter.id)
            .order_by(Chapter.position, Chapter.created_at).all()
        )
        for child in children:
            walk_chapter(child, depth + 1)

    def walk_folder(folder, depth, *, is_book=False):
        if folder.id in seen_folders:
            return
        seen_folders.add(folder.id)
        add_item('book' if is_book else 'folder', folder, depth)
        subfolders = (
            Folder.query.filter_by(parent_id=folder.id)
            .order_by(Folder.position, Folder.created_at).all()
        )
        for child in subfolders:
            walk_folder(child, depth + 1)
        chapters = (
            Chapter.query.filter_by(folder_id=folder.id)
            .order_by(Chapter.position, Chapter.created_at).all()
        )
        for chapter in chapters:
            walk_chapter(chapter, depth + 1)

    for book in ordered_accessible_books():
        walk_folder(book, 0, is_book=True)

    shared_folders, shared_chapters = shared_items()
    narrow_roots = []
    for folder in shared_folders:
        parent = db.session.get(Folder, folder.parent_id)
        if parent is None or role_for_folder(parent) is None:
            narrow_roots.append(('folder', folder))
    for chapter in shared_chapters:
        if chapter.folder_id is not None:
            parent = db.session.get(Folder, chapter.folder_id)
            parent_accessible = parent is not None and role_for_folder(parent) is not None
        else:
            parent = db.session.get(Chapter, chapter.parent_chapter_id)
            parent_accessible = parent is not None and role_for_chapter(parent) is not None
        if not parent_accessible:
            narrow_roots.append(('chapter', chapter))

    def narrow_root_sort_key(entry):
        book = db.session.get(Folder, entry[1].book_id)
        return ((book.name if book is not None else '').lower(), entry[1].name.lower())

    narrow_roots.sort(key=narrow_root_sort_key)
    for target_type, target in narrow_roots:
        if target_type == 'folder':
            walk_folder(target, 0)
        else:
            walk_chapter(target, 0)
    return items


def resource_breadcrumb(folder: Folder | None = None, chapter: Chapter | None = None) -> list:
    """Ancestor folders from the book root down to (but not including) the
    resource itself -- empty for a book (no ancestors) or anything sitting
    directly in a book's root. Only the book entry carries a color, same
    isBook-gated convention as goal_resource_info/FolderTreeNode."""
    if chapter is not None:
        start = nearest_folder_for_chapter(chapter)
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
    today = user_local_today(goal.user)
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
        # Live progress for the *current* period has no upper bound -- "now"
        # is the bound, same as period_end being in the future doesn't cap
        # activity that hasn't happened yet. See Goal's docstring: this is
        # gross typed-word activity by this user, not net resource growth.
        current = resource_typed_words(
            folder=goal.folder, chapter=goal.chapter, user_id=goal.user_id,
            start_date=goal.period_start, end_date=min(period_end, today) if period_end else today,
        )
    else:
        current = resource_completed_chapter_count(goal.folder, goal.period_start, user=goal.user)
    percent = min(100, round(current / goal.target * 100)) if goal.target > 0 else 0
    return {
        'current': current,
        'percent': percent,
        'periodStart': goal.period_start.isoformat(),
        'periodEnd': period_end.isoformat() if period_end else None,
        'achieved': current >= goal.target,
        'started': goal.goal_type != GoalType.words or today >= goal.period_start,
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


def settings_to_dict(settings: UserSettings, user: User) -> dict:
    return {
        # P1.1A: stored on User (a shared Journal reads the *Book owner's*
        # row -- see journal_write_today/format_journal_time), not
        # UserSettings, but exposed through this same settings response
        # since the Settings page saves everything through one call.
        'journalDateFormat': user.journal_date_format,
        'journalTimeFormat': user.journal_time_format,
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
        'showWordCount': settings.show_word_count,
        'showAverageWpm': settings.show_average_wpm,
        'openBookIds': settings.open_book_ids,
        'closedFolderIds': settings.closed_folder_ids,
        'closedChapterIds': settings.closed_chapter_ids,
        'bookOrder': settings.book_order,
        'hiddenGoalIds': settings.hidden_goal_ids,
        'goalOrder': settings.goal_order,
        'primaryGoalId': settings.primary_goal_id,
    }


# ---------------------------------------------------------------- auth --

@api_bp.route('/auth/version')
def api_version():
    return jsonify({'version': VERSION})


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
    return jsonify(me_to_dict(user))


@api_bp.route('/auth/logout', methods=['POST'])
def api_logout():
    logout_user()
    return ('', 204)


@api_bp.route('/auth/me')
def api_me():
    if not current_user.is_authenticated:
        return error('Not authenticated', 401)
    return jsonify(me_to_dict(current_user))


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
    return jsonify(me_to_dict(user))


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


# -------------------------------------------------- internal references --

@api_bp.route('/internal-references')
def api_internal_reference_picker():
    """Permission-filtered, typed targets for the editor's searchable tree."""
    return jsonify(internal_reference_picker_items())


@api_bp.route('/internal-references/<target_type>/<uuid:target_id>')
def api_resolve_internal_reference(target_type, target_id):
    """Resolve a UUID to its current route without leaking private targets."""
    resolved = internal_reference_resolution(target_type, target_id)
    if resolved is None:
        return error('Reference unavailable', 404)
    return jsonify(resolved)


# ------------------------------------------------------------- stats --
#
# Workspace behavioral stats (goals, streak, heatmap, WPM, active time,
# typed/pasted words, trends, and busiest resource) are personal. Document
# state such as current word/chapter/revision counts remains a resource fact.
# Folder/chapter endpoints expose additive activity totals alongside explicit
# per-contributor rows; WPM is never calculated across contributors.


def goal_hit_rate_dict(user_id) -> dict:
    """Percent of a user's historical recurring-goal periods that were
    achieved, across every goal they own. It starts at zero rows until a
    recurring period elapses post-deploy."""
    rows = (
        GoalPeriodHistory.query.join(Goal, GoalPeriodHistory.goal_id == Goal.id)
        .filter(Goal.user_id == user_id)
        .all()
    )
    total = len(rows)
    achieved = sum(1 for r in rows if r.achieved)
    percent = round(achieved / total * 100) if total > 0 else None
    return {'achieved': achieved, 'total': total, 'percent': percent}


def _week_bounds(offset_weeks: int, today: datetime.date | None = None) -> tuple:
    """(start, end) dates, inclusive, of the week `offset_weeks` weeks back
    from the current one (0 = this week, 1 = last week), Monday-anchored."""
    today = today or user_local_today()
    this_monday = today - datetime.timedelta(days=today.weekday())
    start = this_monday - datetime.timedelta(weeks=offset_weeks)
    return start, start + datetime.timedelta(days=6)


def week_over_week_words_dict(chapter_ids: list, user_id) -> dict:
    """Personal typed-word comparison for the workspace stats view."""
    if not chapter_ids:
        return {'thisWeek': 0, 'lastWeek': 0, 'percentChange': None}
    this_start, this_end = _week_bounds(0)
    last_start, last_end = _week_bounds(1)

    def sum_words(start, end) -> int:
        return int(
            db.session.query(db.func.coalesce(db.func.sum(ChapterWritingActivity.words_typed), 0))
            .filter(
                ChapterWritingActivity.chapter_id.in_(chapter_ids),
                ChapterWritingActivity.user_id == user_id,
                ChapterWritingActivity.date >= start,
                ChapterWritingActivity.date <= end,
            )
            .scalar()
        )

    this_week = sum_words(this_start, this_end)
    last_week = sum_words(last_start, last_end)
    percent_change = round((this_week - last_week) / last_week * 100) if last_week > 0 else None
    return {'thisWeek': this_week, 'lastWeek': last_week, 'percentChange': percent_change}


def writing_heatmap(user_id, chapter_ids=None) -> list:
    """Active seconds by day-of-week and hour-of-day, personal to `user_id`."""
    query = (
        db.session.query(
            db.func.extract('dow', ChapterWritingActivity.date),
            ChapterWritingActivity.hour_of_day,
            db.func.sum(ChapterWritingActivity.active_seconds),
        )
        .filter(ChapterWritingActivity.user_id == user_id)
        .group_by(db.func.extract('dow', ChapterWritingActivity.date), ChapterWritingActivity.hour_of_day)
    )
    if chapter_ids is not None:
        chapter_ids = list(chapter_ids)
        if not chapter_ids:
            return []
        query = query.filter(ChapterWritingActivity.chapter_id.in_(chapter_ids))
    rows = query.all()
    # Postgres EXTRACT(DOW) is 0=Sunday..6=Saturday; normalize to Python's
    # date.weekday() convention (0=Monday..6=Sunday) so the frontend only
    # ever deals with one convention.
    return [
        {'dayOfWeek': (int(dow) + 6) % 7, 'hour': hour, 'activeSeconds': int(seconds)}
        for dow, hour, seconds in rows
    ]


def busiest_resource_dict(chapter_ids: list, days: int, user_id):
    if not chapter_ids:
        return None
    query = db.session.query(
        ChapterWritingActivity.chapter_id, db.func.sum(ChapterWritingActivity.active_seconds)
    ).filter(
        ChapterWritingActivity.chapter_id.in_(chapter_ids),
        ChapterWritingActivity.user_id == user_id,
    )
    if days > 0:
        cutoff = user_local_today() - datetime.timedelta(days=days - 1)
        query = query.filter(ChapterWritingActivity.date >= cutoff)
    row = (
        query.group_by(ChapterWritingActivity.chapter_id)
        .order_by(db.func.sum(ChapterWritingActivity.active_seconds).desc())
        .first()
    )
    if row is None:
        return None
    chapter_id, active_seconds = row
    chapter = db.session.get(Chapter, chapter_id)
    if chapter is None:
        return None
    return {'chapterId': chapter.id, 'name': chapter.name, 'activeSeconds': int(active_seconds)}


def writing_wpm(chapter_ids: list, user_id) -> float | None:
    """Per-user WPM. A user id is mandatory so WPM can never be blended."""
    totals = writing_activity_totals(chapter_ids, user_id=user_id)
    return calculate_wpm(totals['wordsTyped'], totals['activeSeconds'])


def total_active_seconds_for(chapter_ids: list, user_id) -> int:
    """Per-user active time; a user id is mandatory just as it is for WPM."""
    return writing_activity_totals(chapter_ids, user_id=user_id)['activeSeconds']


def words_written_in_window(chapter_ids: list, days: int) -> int:
    """Resource-level net "words written" (typed minus deleted, floored at 0)
    for a chapter velocity display."""
    cutoff = user_local_today() - datetime.timedelta(days=days - 1)
    return writing_activity_totals(chapter_ids, start_date=cutoff)['wordsWritten']


def personal_writing_totals(chapter_ids: list, user_id) -> dict:
    """All-time (written, pasted, deleted, typed) totals for `user_id` across
    `chapter_ids` -- personal, unlike words_written_in_window above. Backs
    the workspace Stats page's "Words written"/"Words pasted"/"Words deleted"
    tiles."""
    return writing_activity_totals(chapter_ids, user_id=user_id)


def resource_activity_dict(chapter_ids: list) -> dict:
    """Combined additive totals plus separately calculated contributor rows.

    The caller has already authorized access to the resource. Contributor
    rows intentionally do not consult current shares, preserving historical
    attribution after somebody is unshared.
    """
    totals = writing_activity_totals(chapter_ids)
    contributors = writing_activity_contributions(chapter_ids)
    for contribution in contributors:
        contribution['isCurrentUser'] = contribution['userId'] == current_user.id
    mine = next((row.copy() for row in contributors if row['isCurrentUser']), None)
    if mine is None:
        mine = {
            'userId': current_user.id,
            'username': current_user.username,
            'wordsTyped': 0,
            'wordsPasted': 0,
            'activeSeconds': 0,
            'wpm': None,
            'isCurrentUser': True,
        }
    contributors.sort(
        key=lambda row: (not row['isCurrentUser'], row['username'].casefold(), str(row['userId']))
    )
    return {'totals': totals, 'mine': mine, 'contributors': contributors}


@api_bp.route('/stats')
def api_workspace_stats():
    """Same shape as the per-folder/per-chapter stats endpoints, aggregated
    across every book the current user has whole-book access to (their own
    plus ones shared with them) -- the workspace-wide view."""
    days = int(request.args.get('days', 7))
    book_ids = accessible_book_ids()
    chapters = Chapter.query.filter(Chapter.book_id.in_(book_ids)).all() if book_ids else []
    chapter_ids = [c.id for c in chapters]
    total_words = 0
    words_per_day = {}
    for chapter in chapters:
        count = len(html_to_text(chapter.content_html).split())
        total_words += count
        day = user_local_datetime(current_user, chapter.updated_at).date().isoformat()
        words_per_day[day] = words_per_day.get(day, 0) + count
    if days > 0:
        cutoff = (user_local_today() - datetime.timedelta(days=days - 1)).isoformat()
        words_per_day = {d: c for d, c in words_per_day.items() if d >= cutoff}
    personal_totals = personal_writing_totals(chapter_ids, current_user.id)
    return jsonify({
        'totalWords': total_words,
        'chapterCount': len(chapters),
        'completedChapterCount': sum(1 for chapter in chapters if chapter.completed_at is not None),
        'revisionCount': sum(chapter.version_count for chapter in chapters),
        'wordsPerDay': prune_words_per_day(words_per_day),
        'streak': compute_writing_streak(current_user.id, chapter_ids=chapter_ids),
        'goalHitRate': goal_hit_rate_dict(current_user.id),
        'weekOverWeekWords': week_over_week_words_dict(chapter_ids, current_user.id),
        'heatmap': writing_heatmap(current_user.id, chapter_ids),
        'busiestResource': busiest_resource_dict(chapter_ids, days, current_user.id),
        'avgWpm': writing_wpm(chapter_ids, user_id=current_user.id),
        'totalActiveSeconds': total_active_seconds_for(chapter_ids, user_id=current_user.id),
        'wordsTyped': personal_totals['wordsTyped'],
        'wordsPasted': personal_totals['wordsPasted'],
        'wordsDeleted': personal_totals['wordsDeleted'],
        'wordsWritten': personal_totals['wordsWritten'],
    })


@api_bp.route('/books', methods=['POST'])
def api_create_book():
    data = request.get_json(silent=True) or {}
    name = clean_name(data.get('name', ''))
    if not name:
        return error('name is required')
    if Folder.query.filter_by(parent_id=None, name=name).first():
        return error('Name already exists', 409)
    # Plain/direct creation defaults to 'general' -- the interactive New
    # Book wizard (api_create_book_wizard) is what defaults to 'novel'.
    book_type = data.get('bookType', 'general')
    if book_type not in BOOK_TYPES:
        return error('Invalid bookType')
    book = create_book(name, owner_id=current_user.id, book_type=book_type)
    settings = get_user_settings()
    settings.open_book_ids = settings.open_book_ids + [book.id]
    db.session.commit()
    return jsonify(book_to_dict(book)), 201


@api_bp.route('/books/<uuid:book_id>')
def api_get_book(book_id):
    book = require_book_access(book_id, 'viewer')
    return jsonify(book_to_dict(book))


@api_bp.route('/books/<uuid:book_id>', methods=['PATCH'])
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
    if 'showBookColor' in data:
        book.show_book_color = bool(data['showBookColor'])
    if 'bookType' in data:
        # Changing Book Type is metadata-only -- see Folder.book_type's
        # docstring and journal_write_today. Never touches content,
        # hierarchy, goals, or statistics, and is immediately reversible.
        if data['bookType'] not in BOOK_TYPES:
            return error('Invalid bookType')
        book.book_type = data['bookType']
    db.session.commit()
    return jsonify(book_to_dict(book))


@api_bp.route('/books/<uuid:book_id>', methods=['DELETE'])
def api_delete_book(book_id):
    book = require_book_access(book_id, 'owner')
    db.session.delete(book)
    db.session.commit()
    return ('', 204)


@api_bp.route('/books/wizard', methods=['POST'])
def api_create_book_wizard():
    """The interactive New Book modal's creation endpoint. `bookType`
    defaults to 'novel' when omitted, preserving the original creation
    scaffold (Chapters folder + Chapter One + selected extras) exactly for
    any existing caller that doesn't send it -- see P1.2's "do not silently
    change callers that currently depend on the existing Novel wizard
    scaffolding". A non-Novel type creates only the root Book: Journal's
    year/month/day hierarchy is built lazily by the first Write Today, not
    at creation time; Documentation/General start genuinely empty in v1."""
    data = request.get_json(silent=True) or {}
    title = clean_name(data.get('title', ''))
    author_text = (data.get('author') or '').strip()
    color_value = (data.get('color') or '#dddddd').strip()
    book_type = data.get('bookType') or 'novel'
    if book_type not in BOOK_TYPES:
        return error('Invalid bookType')
    if not title:
        return error('title is required')
    if Folder.query.filter_by(parent_id=None, name=title).first():
        return error('Name already exists', 409)
    book = create_book(title, owner_id=current_user.id, author=author_text, color=color_value, book_type=book_type)
    if book_type == 'novel':
        chapters_name = clean_name(data.get('chapters', 'Chapters'))
        extras = data.get('extras') or []
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


@api_bp.route('/books/<uuid:book_id>/journal/today', methods=['POST'])
def api_journal_write_today(book_id):
    """P1.2 "Write Today": finds or creates the Book owner's local today's
    Journal Chapter (year/month/day hierarchy created lazily on first use --
    see journal_write_today). Editor-or-higher only; a Viewer can read
    Journal content but never triggers creation/continuation of an entry.
    The response hands the frontend everything needed to navigate there and
    append exactly one client-side timestamp (never inserted here -- see
    ChapterEditor's Journal handoff) without double-appending across
    Strict Mode/rerenders: a fresh entryRequestId per successful call."""
    book = require_book_access(book_id, 'editor')
    if (book.book_type or 'general') != 'journal':
        return error('This book is not a Journal')
    try:
        chapter, created = journal_write_today(book)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return error("Couldn't create today's Journal entry.", 500)
    owner = db.session.get(User, book.owner_id)
    owner_timezone = owner.timezone if owner is not None and is_valid_timezone(owner.timezone) else 'UTC'
    entry_timestamp = datetime.datetime.now(datetime.timezone.utc)
    # P1.1A: pre-formatted using the Book *owner's* time-format preference
    # (never the requesting Editor's) so every collaborator's client
    # inserts an identical label regardless of their own browser locale/
    # settings -- see format_journal_time. The raw entryTimestamp/
    # journalTimezone fields stay for compatibility/diagnostics.
    owner_time_format = owner.journal_time_format if owner is not None else DEFAULT_JOURNAL_TIME_FORMAT
    entry_time_label = format_journal_time(entry_timestamp, owner_timezone, owner_time_format)
    return jsonify({
        'chapter': chapter_summary_dict(chapter),
        'created': created,
        'journalDate': chapter.journal_date.isoformat(),
        'entryRequestId': str(uuid.uuid4()),
        'entryTimestamp': entry_timestamp.isoformat(),
        'entryTimeLabel': entry_time_label,
        'journalTimezone': owner_timezone,
    })


@api_bp.route('/books/<uuid:book_id>/export.docx')
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


@api_bp.route('/folders/<uuid:folder_id>/shares')
def api_list_folder_shares(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    require_folder_share_management(folder)
    rows = ResourceShare.query.filter_by(folder_id=folder_id).all()
    return jsonify([share_dict(r) for r in rows])


@api_bp.route('/folders/<uuid:folder_id>/shares', methods=['POST'])
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


@api_bp.route('/folders/<uuid:folder_id>/shares/<uuid:user_id>', methods=['PATCH'])
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


@api_bp.route('/folders/<uuid:folder_id>/shares/<uuid:user_id>', methods=['DELETE'])
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


@api_bp.route('/chapters/<uuid:chapter_id>/shares')
def api_list_chapter_shares(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    require_chapter_share_management(chapter)
    rows = ResourceShare.query.filter_by(chapter_id=chapter_id).all()
    return jsonify([share_dict(r) for r in rows])


@api_bp.route('/chapters/<uuid:chapter_id>/shares', methods=['POST'])
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


@api_bp.route('/chapters/<uuid:chapter_id>/shares/<uuid:user_id>', methods=['PATCH'])
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


@api_bp.route('/chapters/<uuid:chapter_id>/shares/<uuid:user_id>', methods=['DELETE'])
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

@api_bp.route('/folders/<uuid:folder_id>')
def api_get_folder(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    subfolders = Folder.query.filter_by(parent_id=folder.id).order_by(Folder.position, Folder.created_at).all()
    chapters = Chapter.query.filter_by(folder_id=folder.id).order_by(Chapter.position, Chapter.created_at).all()
    with_children = chapter_ids_with_children([c.id for c in chapters])
    d = folder_to_dict(folder)
    d['folders'] = [folder_to_dict(f) for f in subfolders]
    d['chapters'] = [chapter_summary_dict(c, has_children=c.id in with_children) for c in chapters]
    return jsonify(d)


@api_bp.route('/folders/<uuid:folder_id>/tree-ids')
def api_folder_tree_ids(folder_id):
    """Every sub-folder and chapter id nested under this folder (not
    including the folder itself) -- for "Open all", which un-hides a whole
    subtree from the sidebar in one action."""
    folder = require_folder_access(folder_id, 'viewer')
    folder_ids = [fid for fid in descendant_folder_ids(folder.id) if fid != folder.id]
    chapter_ids = chapter_ids_under_folder(folder.id)
    return jsonify({'folderIds': folder_ids, 'chapterIds': chapter_ids})


@api_bp.route('/folders/<uuid:folder_id>/tree')
def api_folder_tree(folder_id):
    """Every sub-folder and chapter nested under this folder (not including
    the folder itself), flattened depth-first with a name and depth on each
    entry -- for a picker that needs to let someone choose any sub-folder or
    chapter within a book in one dropdown (see the goal-creation modal),
    where tree-ids' bare id lists aren't enough."""
    folder = require_folder_access(folder_id, 'viewer')
    entries = []

    def walk_chapter_children(parent_chapter_id, depth):
        children = (
            Chapter.query.filter_by(parent_chapter_id=parent_chapter_id)
            .order_by(Chapter.position, Chapter.created_at).all()
        )
        for c in children:
            entries.append({'id': c.id, 'type': 'chapter', 'name': c.name, 'depth': depth})
            walk_chapter_children(c.id, depth + 1)

    def walk(parent_id, depth):
        subfolders = Folder.query.filter_by(parent_id=parent_id).order_by(Folder.position, Folder.created_at).all()
        for f in subfolders:
            entries.append({'id': f.id, 'type': 'folder', 'name': f.name, 'depth': depth})
            walk(f.id, depth + 1)
        chapters = Chapter.query.filter_by(folder_id=parent_id).order_by(Chapter.position, Chapter.created_at).all()
        for c in chapters:
            entries.append({'id': c.id, 'type': 'chapter', 'name': c.name, 'depth': depth})
            walk_chapter_children(c.id, depth + 1)

    walk(folder.id, 0)
    return jsonify(entries)


@api_bp.route('/folders/<uuid:folder_id>/stats')
def api_folder_stats(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    days = int(request.args.get('days', 7))
    chapter_ids = chapter_ids_under_folder(folder.id)
    chapters = Chapter.query.filter(Chapter.id.in_(chapter_ids)).all()
    total_words = 0
    words_per_day = {}
    word_counts = {}
    for chapter in chapters:
        count = len(html_to_text(chapter.content_html).split())
        word_counts[chapter.id] = count
        total_words += count
        day = user_local_datetime(current_user, chapter.updated_at).date().isoformat()
        words_per_day[day] = words_per_day.get(day, 0) + count
    if days > 0:
        cutoff = (user_local_today() - datetime.timedelta(days=days - 1)).isoformat()
        words_per_day = {d: c for d, c in words_per_day.items() if d >= cutoff}

    # "Spread within a sub-folder" reads as sibling comparison -- direct
    # children only, not the full recursive subtree.
    direct_counts = [word_counts[c.id] for c in chapters if c.folder_id == folder.id]
    word_count_spread = (
        {'min': min(direct_counts), 'max': max(direct_counts), 'avg': round(sum(direct_counts) / len(direct_counts))}
        if direct_counts else None
    )

    today = user_local_today()
    stale_cutoff = today - datetime.timedelta(days=STALE_CHAPTER_DAYS)
    stale_chapters = []
    for chapter in chapters:
        if chapter.completed_at is not None:
            continue
        last_activity = chapter_last_activity_date(chapter, current_user)
        if last_activity is not None and last_activity <= stale_cutoff:
            stale_chapters.append({
                'id': chapter.id,
                'name': chapter.name,
                'daysSinceActivity': (today - last_activity).days,
            })
    stale_chapters.sort(key=lambda c: -c['daysSinceActivity'])

    chapter_breakdown = [
        {
            'id': chapter.id,
            'name': chapter.name,
            'versionCount': chapter.version_count,
            'recentVelocity7d': words_written_in_window([chapter.id], 7),
            'recentVelocity30d': words_written_in_window([chapter.id], 30),
            'wpm': writing_wpm([chapter.id], current_user.id),
        }
        for chapter in chapters
    ]
    return jsonify({
        'totalWords': total_words,
        'chapterCount': len(chapters),
        'completedChapterCount': sum(1 for chapter in chapters if chapter.completed_at is not None),
        'revisionCount': sum(chapter.version_count for chapter in chapters),
        'activity': resource_activity_dict(chapter_ids),
        'wordsPerDay': prune_words_per_day(words_per_day),
        'staleChapters': stale_chapters,
        'wordCountSpread': word_count_spread,
        'chapters': chapter_breakdown,
    })


@api_bp.route('/folders', methods=['POST'])
def api_create_folder():
    data = request.get_json(silent=True) or {}
    name = clean_name(data.get('name', ''))
    parent_id = parse_uuid(data.get('parentId'))
    if not parent_id or not name:
        return error('parentId and name are required')
    parent = require_folder_access(parent_id, 'editor')
    validate_folder_parent(None, parent)
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


@api_bp.route('/folders/<uuid:folder_id>', methods=['PATCH'])
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
    if 'showBookColor' in data:
        folder.show_book_color = bool(data['showBookColor'])
    if 'parentId' in data:
        new_parent_id = parse_uuid(data['parentId'])
        if new_parent_id is None:
            return error('parentId must be a valid id')
        new_parent = require_folder_access(new_parent_id, 'editor')
        if new_parent.id != folder.parent_id:
            lock_books_for_hierarchy_change(folder.book_id)
            validate_folder_parent(folder.id, new_parent)
            if Folder.query.filter_by(parent_id=new_parent.id, name=folder.name).first():
                return error('Name already exists in destination', 409)
            folder.parent_id = new_parent.id
            folder.position = next_folder_position(new_parent.id)
    db.session.commit()
    return jsonify(folder_to_dict(folder))


@api_bp.route('/folders/<uuid:folder_id>', methods=['DELETE'])
def api_delete_folder(folder_id):
    folder = require_folder_access(folder_id, 'editor')
    db.session.delete(folder)
    db.session.commit()
    return ('', 204)


@api_bp.route('/folders/<uuid:folder_id>/export.docx')
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


@api_bp.route('/folders/<uuid:folder_id>/export.rtf')
def api_export_folder_rtf(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    book = db.session.get(Folder, folder.book_id)
    chapters = folder_chapters_recursive(folder_id)
    bio = BytesIO(render_folder_rtf(folder.name, chapters))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, folder.name, 'rtf'),
                      mimetype='application/rtf')


@api_bp.route('/folders/<uuid:folder_id>/export.txt')
def api_export_folder_txt(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    book = db.session.get(Folder, folder.book_id)
    chapters = folder_chapters_recursive(folder_id)
    bio = BytesIO(render_folder_txt(folder.name, chapters).encode('utf-8'))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, folder.name, 'txt'),
                      mimetype='text/plain')


@api_bp.route('/folders/<uuid:folder_id>/export.md')
def api_export_folder_md(folder_id):
    folder = require_folder_access(folder_id, 'viewer')
    book = db.session.get(Folder, folder.book_id)
    chapters = folder_chapters_recursive(folder_id)
    bio = BytesIO(render_folder_markdown(folder.name, chapters).encode('utf-8'))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, folder.name, 'md'),
                      mimetype='text/markdown')


@api_bp.route('/folders/<uuid:folder_id>/reorder', methods=['POST'])
def api_reorder_folder(folder_id):
    folder = require_folder_access(folder_id, 'editor')
    data = request.get_json(silent=True) or {}
    typ = data.get('type')
    ids_order = [i for i in (parse_uuid(raw) for raw in data.get('order', [])) if i is not None]
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


@api_bp.route('/chapters/<uuid:chapter_id>/reorder', methods=['POST'])
def api_reorder_chapter_children(chapter_id):
    """Mirrors api_reorder_folder above, scoped to a parent chapter's own
    child chapters instead of a folder's -- needed now that a chapter can
    have its own ordered child-chapter list. Sibling reorder only, same as
    api_reorder_folder: never changes parentage."""
    chapter = require_chapter_access(chapter_id, 'editor')
    data = request.get_json(silent=True) or {}
    ids_order = [i for i in (parse_uuid(raw) for raw in data.get('order', [])) if i is not None]
    children = Chapter.query.filter_by(parent_chapter_id=chapter.id).all()
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
    name = clean_name(data.get('name', ''))
    folder_id = parse_uuid(data.get('folderId'))
    parent_chapter_id = parse_uuid(data.get('parentChapterId'))
    if not name or (folder_id is None) == (parent_chapter_id is None):
        return error('Exactly one of folderId/parentChapterId, plus name, are required')

    if folder_id is not None:
        folder = require_folder_access(folder_id, 'editor')
        parent_chapter = None
    else:
        parent_chapter = require_chapter_access(parent_chapter_id, 'editor')
        folder = None

    validate_chapter_parent(None, new_folder=folder, new_parent_chapter=parent_chapter)

    if folder is not None:
        if Chapter.query.filter_by(folder_id=folder.id, name=name).first():
            return error('Name already exists', 409)
        chapter = Chapter(
            folder_id=folder.id, book_id=folder.book_id, name=name,
            description=data.get('description', ''), position=next_chapter_position(folder_id=folder.id),
        )
    else:
        if Chapter.query.filter_by(parent_chapter_id=parent_chapter.id, name=name).first():
            return error('Name already exists', 409)
        chapter = Chapter(
            parent_chapter_id=parent_chapter.id, book_id=parent_chapter.book_id, name=name,
            description=data.get('description', ''),
            position=next_chapter_position(parent_chapter_id=parent_chapter.id),
        )
    db.session.add(chapter)
    db.session.commit()
    return jsonify(chapter_detail_dict(chapter)), 201


@api_bp.route('/chapters/<uuid:chapter_id>')
def api_get_chapter(chapter_id):
    chapter = require_chapter_access(chapter_id, 'viewer')
    return jsonify(chapter_detail_dict(chapter))


@api_bp.route('/chapters/<uuid:chapter_id>/tree-children')
def api_chapter_tree_children(chapter_id):
    """A chapter's own direct child chapters, for the sidebar tree -- same
    shape/purpose as GET /folders/<id>'s `.chapters`, kept as a separate
    lightweight endpoint so expanding a tree node doesn't pull contentHtml/
    notesText along with it."""
    chapter = require_chapter_access(chapter_id, 'viewer')
    children = (
        Chapter.query.filter_by(parent_chapter_id=chapter.id).order_by(Chapter.position, Chapter.created_at).all()
    )
    with_children = chapter_ids_with_children([c.id for c in children])
    return jsonify({'chapters': [chapter_summary_dict(c, has_children=c.id in with_children) for c in children]})


@api_bp.route('/chapters/<uuid:chapter_id>', methods=['PATCH'])
def api_update_chapter(chapter_id):
    chapter = require_chapter_access(chapter_id, 'editor')
    data = request.get_json(silent=True) or {}
    if 'expectedUpdatedAt' in data and not _matches_updated_at(chapter, data['expectedUpdatedAt']):
        return error('This chapter was changed elsewhere. Reload to see the latest version.', 409)
    if 'name' in data:
        new_name = clean_name(data['name'])
        if not new_name:
            return error('name cannot be empty')
        # Scoped to whichever immediate parent this chapter actually has --
        # a nested chapter's folder_id is NULL, so filtering on it directly
        # would compare against every other NULL-folder_id chapter in the
        # app instead of this chapter's own siblings.
        sibling_filter = (
            {'folder_id': chapter.folder_id} if chapter.folder_id is not None
            else {'parent_chapter_id': chapter.parent_chapter_id}
        )
        if new_name != chapter.name and Chapter.query.filter_by(name=new_name, **sibling_filter).first():
            return error('Name already exists', 409)
        chapter.name = new_name
    if 'description' in data:
        chapter.description = data['description']
    if 'folderId' in data and 'parentChapterId' in data:
        return error('Set at most one of folderId/parentChapterId')
    if 'folderId' in data or 'parentChapterId' in data:
        new_folder_id = parse_uuid(data['folderId']) if 'folderId' in data else None
        new_parent_chapter_id = parse_uuid(data['parentChapterId']) if 'parentChapterId' in data else None
        if ('folderId' in data and new_folder_id is None) or ('parentChapterId' in data and new_parent_chapter_id is None):
            return error('folderId/parentChapterId must be a valid id')
        new_folder = require_folder_access(new_folder_id, 'editor') if new_folder_id is not None else None
        new_parent_chapter = (
            require_chapter_access(new_parent_chapter_id, 'editor') if new_parent_chapter_id is not None else None
        )
        new_book_id = new_folder.book_id if new_folder is not None else new_parent_chapter.book_id
        if new_folder_id != chapter.folder_id or new_parent_chapter_id != chapter.parent_chapter_id:
            lock_books_for_hierarchy_change(chapter.book_id, new_book_id)
            validate_chapter_parent(chapter.id, new_folder=new_folder, new_parent_chapter=new_parent_chapter)
            sibling_filter = (
                {'folder_id': new_folder.id} if new_folder is not None else {'parent_chapter_id': new_parent_chapter.id}
            )
            if Chapter.query.filter_by(name=chapter.name, **sibling_filter).first():
                return error('Name already exists in destination', 409)
            chapter.folder_id = new_folder.id if new_folder is not None else None
            chapter.parent_chapter_id = new_parent_chapter.id if new_parent_chapter is not None else None
            chapter.position = next_chapter_position(
                folder_id=(new_folder.id if new_folder is not None else None),
                parent_chapter_id=(new_parent_chapter.id if new_parent_chapter is not None else None),
            )
            if new_book_id != chapter.book_id:
                # Cross-book chapter moves are allowed (existing behavior) --
                # cascade book_id onto the entire moved subtree, not just
                # this row, in the same transaction as the reparent.
                subtree_ids = descendant_chapter_ids(chapter.id)
                Chapter.query.filter(Chapter.id.in_(subtree_ids)).update(
                    {'book_id': new_book_id}, synchronize_session=False
                )
                chapter.book_id = new_book_id
    if 'contentHtml' in data:
        new_content = sanitize_html(data['contentHtml'])
        if new_content != chapter.content_html:
            snapshot_chapter_version(chapter)
            chapter.content_html = new_content
    if 'notesText' in data:
        chapter.notes_text = data['notesText']
    if 'showBookColor' in data:
        chapter.show_book_color = bool(data['showBookColor'])
    if 'completed' in data:
        if data['completed']:
            if chapter.completed_at is None:
                chapter.completed_at = datetime.datetime.now(datetime.timezone.utc)
        else:
            chapter.completed_at = None
    db.session.commit()
    return jsonify(chapter_detail_dict(chapter))


@api_bp.route('/chapters/<uuid:chapter_id>', methods=['DELETE'])
def api_delete_chapter(chapter_id):
    chapter = require_chapter_access(chapter_id, 'editor')
    if Chapter.query.filter_by(parent_chapter_id=chapter.id).first() is not None:
        return error("Can't delete this chapter while it contains sub-chapters. Move or delete its sub-chapters first.")
    db.session.delete(chapter)
    db.session.commit()
    return ('', 204)


@api_bp.route('/chapters/<uuid:chapter_id>/export.docx')
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


@api_bp.route('/chapters/<uuid:chapter_id>/export.rtf')
def api_export_chapter_rtf(chapter_id):
    chapter = require_chapter_access(chapter_id, 'viewer')
    book = db.session.get(Folder, chapter.book_id)
    bio = BytesIO(render_chapter_rtf(chapter.content_html))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, chapter.name, 'rtf'),
                      mimetype='application/rtf')


@api_bp.route('/chapters/<uuid:chapter_id>/export.txt')
def api_export_chapter_txt(chapter_id):
    chapter = require_chapter_access(chapter_id, 'viewer')
    book = db.session.get(Folder, chapter.book_id)
    bio = BytesIO(html_to_text(chapter.content_html).encode('utf-8'))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, chapter.name, 'txt'),
                      mimetype='text/plain')


@api_bp.route('/chapters/<uuid:chapter_id>/export.md')
def api_export_chapter_md(chapter_id):
    chapter = require_chapter_access(chapter_id, 'viewer')
    book = db.session.get(Folder, chapter.book_id)
    bio = BytesIO(html_to_markdown(chapter.content_html).encode('utf-8'))
    return send_file(bio, as_attachment=True, download_name=export_filename(book, chapter.name, 'md'),
                      mimetype='text/markdown')


@api_bp.route('/chapters/<uuid:chapter_id>/versions')
def api_list_chapter_versions(chapter_id):
    require_chapter_access(chapter_id, 'viewer')
    versions = (
        ChapterVersion.query.filter_by(chapter_id=chapter_id)
        .order_by(ChapterVersion.created_at.desc())
        .all()
    )
    return jsonify([chapter_version_summary_dict(v) for v in versions])


@api_bp.route('/chapters/<uuid:chapter_id>/versions/<uuid:version_id>')
def api_get_chapter_version(chapter_id, version_id):
    require_chapter_access(chapter_id, 'viewer')
    version = ChapterVersion.query.filter_by(id=version_id, chapter_id=chapter_id).first_or_404()
    d = chapter_version_summary_dict(version)
    d['contentHtml'] = version.content_html
    return jsonify(d)


@api_bp.route('/chapters/<uuid:chapter_id>/versions/<uuid:version_id>/restore', methods=['POST'])
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


@api_bp.route('/chapters/<uuid:chapter_id>/stats')
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
        day = user_local_datetime(current_user, version.created_at).date().isoformat()
        words_per_day[day] = len(html_to_text(version.content_html).split())
    total_words = len(html_to_text(chapter.content_html).split())
    today = user_local_today()
    words_per_day[today.isoformat()] = total_words
    if days > 0:
        cutoff = (today - datetime.timedelta(days=days - 1)).isoformat()
        words_per_day = {d: c for d, c in words_per_day.items() if d >= cutoff}
    return jsonify({
        'totalWords': total_words,
        'wordsPerDay': prune_words_per_day(words_per_day),
        'activity': resource_activity_dict([chapter.id]),
    })


PRESENCE_RECENT_WINDOW = datetime.timedelta(seconds=30)


@api_bp.route('/chapters/<uuid:chapter_id>/presence', methods=['POST'])
def api_heartbeat_chapter_presence(chapter_id):
    """Also the carrier for input-source-aware writing-activity tracking.
    `wordCount` is the chapter's live total, diffed against the
    last-recorded `last_word_count` the same way it always has been.
    `typedWordsTotal`/`pastedWordsTotal`/`deletedWordsTotal` are cumulative
    *since the editor mounted* (never reset by the client mid-session -- see
    ChapterPage.tsx), diffed the identical way against
    `last_typed_words`/`last_pasted_words`/`last_deleted_words`. This makes
    the transport self-healing: a dropped heartbeat's words aren't lost (the
    next successful heartbeat's larger cumulative total catches the server
    up), and a duplicated heartbeat can't double-credit (the same cumulative
    value diffs to zero the second time). A page reload resets the client's
    counters to 0, which briefly diffs negative against a nonzero
    last_recorded value -- clamped to 0 (no phantom credit) and
    self-corrects on the very next heartbeat, since last_recorded is always
    unconditionally overwritten with the current total regardless of
    direction.

    `hadTypingInput` -- true only for genuine keyboard/composition input
    this interval, false for paste/drop/undo/redo/formatting/programmatic
    (see ChapterEditor.tsx's classifier) -- is what gates active_seconds.
    This is deliberately NOT "typedWordsTotal or pastedWordsTotal changed":
    a paste-only interval must still credit pastedWords (for the stat) but
    must NOT grow active_seconds, or WPM's denominator would be inflated by
    time spent pasting rather than typing.

    Presence creation is an INSERT .. ON CONFLICT DO NOTHING followed by a
    SELECT .. FOR UPDATE. That one-row lock serializes both first-heartbeat
    races and subsequent counter accounting; duplicate or overlapping
    requests can therefore neither violate the unique constraint nor credit
    the same cumulative delta twice."""
    chapter = require_chapter_access(chapter_id, 'viewer')
    data = request.get_json(silent=True) or {}
    raw_word_count = data.get('wordCount')
    word_count = (
        int(raw_word_count) if isinstance(raw_word_count, (int, float)) and not isinstance(raw_word_count, bool) else None
    )

    def as_nonneg_int(value) -> int:
        return max(0, int(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0

    typed_words_total = as_nonneg_int(data.get('typedWordsTotal'))
    pasted_words_total = as_nonneg_int(data.get('pastedWordsTotal'))
    deleted_words_total = as_nonneg_int(data.get('deletedWordsTotal'))
    had_typing_input = bool(data.get('hadTypingInput'))

    # The unique (chapter_id, user_id) identity is the concurrency boundary.
    # ON CONFLICT makes simultaneous first heartbeats safe; FOR UPDATE then
    # serializes all counter reads, activity credit, and counter advancement
    # for an existing row. record_writing_activity uses this same session and
    # never commits, so both records succeed or fail together at the one
    # commit below.
    insert_result = db.session.execute(
        pg_insert(ChapterPresence)
        .values(
            chapter_id=chapter_id,
            user_id=current_user.id,
            last_word_count=word_count,
            last_typed_words=typed_words_total,
            last_pasted_words=pasted_words_total,
            last_deleted_words=deleted_words_total,
        )
        .on_conflict_do_nothing(
            index_elements=[ChapterPresence.chapter_id, ChapterPresence.user_id]
        )
    )
    inserted = insert_result.rowcount == 1
    row = db.session.execute(
        db.select(ChapterPresence)
        .where(
            ChapterPresence.chapter_id == chapter_id,
            ChapterPresence.user_id == current_user.id,
        )
        .with_for_update()
    ).scalar_one()

    now = datetime.datetime.now(datetime.timezone.utc)
    if word_count is not None:
        # A newly inserted row establishes the cumulative baseline; it has
        # no previous interval to credit. Every later request reaches this
        # calculation only while holding the row lock.
        if not inserted:
            last_seen = row.last_seen
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=datetime.timezone.utc)
            elapsed = min((now - last_seen).total_seconds(), MAX_HEARTBEAT_ELAPSED.total_seconds())
            typed_delta = max(0, typed_words_total - row.last_typed_words)
            pasted_delta = max(0, pasted_words_total - row.last_pasted_words)
            deleted_delta = max(0, deleted_words_total - row.last_deleted_words)
            # Active seconds gate on genuine typing input alone -- a
            # paste-only interval still credits pasted_delta, just with 0
            # elapsed, so it can never inflate WPM's active-time denominator.
            elapsed_for_activity = elapsed if had_typing_input else 0
            if had_typing_input or typed_delta > 0 or pasted_delta > 0 or deleted_delta > 0:
                record_writing_activity(
                    chapter, current_user.id, elapsed_for_activity, typed_delta, pasted_delta, deleted_delta
                )
        row.last_word_count = word_count
        row.last_typed_words = typed_words_total
        row.last_pasted_words = pasted_words_total
        row.last_deleted_words = deleted_words_total
    row.last_seen = now
    db.session.commit()
    return jsonify({'averageWpm': writing_wpm([chapter.id], current_user.id)})


@api_bp.route('/chapters/<uuid:chapter_id>/presence')
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
    resource_id = parse_uuid(data.get('resourceId'))
    goal_type = data.get('goalType')
    target = data.get('target')
    cadence = data.get('cadence')
    start_date_raw = data.get('startDate')
    end_date_raw = data.get('endDate')
    name = clean_name(data.get('name') or '')

    if resource_type not in ('folder', 'chapter'):
        return error('resourceType must be "folder" or "chapter"')
    if resource_id is None:
        return error('resourceId must be a valid id')
    if goal_type not in ('words', 'chapters'):
        return error('goalType must be "words" or "chapters"')
    if goal_type == 'chapters' and resource_type != 'folder':
        return error('Chapter-count goals can only be set on a book or folder')
    if not isinstance(target, int) or isinstance(target, bool) or target <= 0:
        return error('target must be a positive integer')

    if resource_type == 'folder':
        folder = require_folder_access(resource_id, 'editor')
        folder_id, chapter_id = folder.id, None
    else:
        chapter = require_chapter_access(resource_id, 'editor')
        folder_id, chapter_id = None, chapter.id

    try:
        start_date = datetime.date.fromisoformat(start_date_raw) if start_date_raw else user_local_today()
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


@api_bp.route('/goals/<uuid:goal_id>', methods=['PATCH'])
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
            # Re-anchor the current period here; advance_goal_period() below
            # will roll it straight past if the new date is already in the
            # past. Progress is a live date-range sum, so there's no
            # baseline to invalidate/recapture.
            goal.start_date = new_start_date
            goal.period_start = new_start_date
        if end_date_provided:
            goal.end_date = new_end_date

    advance_goal_period(goal)
    db.session.commit()
    return jsonify(goal_dict(goal))


@api_bp.route('/goals/<uuid:goal_id>', methods=['DELETE'])
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


@api_bp.route('/goals/<uuid:goal_id>/history')
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

@api_bp.route('/me/timezone', methods=['PATCH'])
def api_update_timezone():
    data = request.get_json(silent=True) or {}
    timezone_name = data.get('timezone')
    if not is_valid_timezone(timezone_name):
        return error('timezone must be a valid IANA timezone')
    # Browser auto-detection is a write-once default. An explicit Settings
    # change omits this flag and remains reversible at any time.
    if not data.get('onlyIfUnset') or current_user.timezone is None:
        current_user.timezone = timezone_name
        db.session.commit()
    return jsonify(me_to_dict(current_user))

@api_bp.route('/me/settings')
def api_get_settings():
    return jsonify(settings_to_dict(get_user_settings(), current_user))


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
        'showWordCount': 'show_word_count',
        'showAverageWpm': 'show_average_wpm',
        'openBookIds': 'open_book_ids',
        'closedFolderIds': 'closed_folder_ids',
        'closedChapterIds': 'closed_chapter_ids',
        'bookOrder': 'book_order',
        'hiddenGoalIds': 'hidden_goal_ids',
        'goalOrder': 'goal_order',
        'primaryGoalId': 'primary_goal_id',
    }
    id_array_keys = {'openBookIds', 'closedFolderIds', 'closedChapterIds', 'bookOrder', 'hiddenGoalIds', 'goalOrder'}
    for api_key, attr in field_map.items():
        if api_key not in data:
            continue
        value = data[api_key]
        if api_key in id_array_keys:
            if not isinstance(value, list):
                return error(f'{api_key} must be a list of ids')
            parsed = [parse_uuid(raw) for raw in value]
            if any(p is None for p in parsed):
                return error(f'{api_key} contains an invalid id')
            value = parsed
        elif api_key == 'primaryGoalId' and value is not None:
            goal_uuid = parse_uuid(value)
            if goal_uuid is None or not Goal.query.filter_by(id=goal_uuid, user_id=current_user.id).first():
                return error('No such goal')
            value = goal_uuid
        if api_key in {'showWordCount', 'showAverageWpm'} and not isinstance(value, bool):
            return error(f'{api_key} must be a boolean')
        setattr(settings, attr, value)
    # WPM is a supporting detail of the word-count footer. Hiding word count
    # always turns WPM off too; re-enabling word count does not silently
    # re-enable WPM, so the two preferences remain predictable.
    if not settings.show_word_count:
        settings.show_average_wpm = False
    # P1.1A: stored on User, not UserSettings (see settings_to_dict) --
    # never trust the frontend dropdown as the only validator. Takes effect
    # immediately for future Journal generation only; never rewrites
    # existing Chapter names/timestamps.
    if 'journalDateFormat' in data:
        if data['journalDateFormat'] not in JOURNAL_DATE_FORMATS:
            return error('Invalid journalDateFormat')
        current_user.journal_date_format = data['journalDateFormat']
    if 'journalTimeFormat' in data:
        if data['journalTimeFormat'] not in JOURNAL_TIME_FORMATS:
            return error('Invalid journalTimeFormat')
        current_user.journal_time_format = data['journalTimeFormat']
    db.session.commit()
    return jsonify(settings_to_dict(settings, current_user))


# -------------------------------------------------------------- search --
#
# Search 2.0 (P1.1). search_tsv (Chapter's PostgreSQL FTS column/index) is
# deliberately NOT consulted here any more -- English FTS drops stop words
# and normalizes tokens in ways that made it an incorrect *gate* for literal
# substring search ("the", punctuation, non-English names). Given this
# app's scale, a straightforward permission-scoped full scan using literal
# case-insensitive matching (see services.find_literal_occurrences) is
# simpler and, more importantly, actually correct; search_tsv itself is
# left in place in case a future optimization wants it back as a candidate
# pre-filter (never as the sole correctness gate).

SEARCH_DEFAULT_LIMIT = 50
SEARCH_MAX_LIMIT = 100
SEARCH_SCOPE_TYPES = {'workspace', 'book', 'folder'}


def _search_scope_chapter_ids(scope_type: str, scope_id) -> list:
    """Chapter ids to search for a scope, already permission-correct.

    require_book_access/require_folder_access 404 (not reveal-why) for a
    scope the current user can't read at all -- "an unavailable scope
    should respond using the application's normal unavailable/not-found
    behavior" -- so an inaccessible Book/Folder scope is simply never
    reachable past this point.
    """
    if scope_type == 'book':
        require_book_access(scope_id, 'viewer')
        # book_id is denormalized onto every chapter regardless of nesting
        # depth (see Chapter's docstring), so this single filter already
        # includes every recursively nested chapter in the book -- no BFS
        # needed the way a specific (possibly non-root) folder scope needs.
        return [row.id for row in Chapter.query.filter_by(book_id=scope_id).with_entities(Chapter.id)]
    if scope_type == 'folder':
        require_folder_access(scope_id, 'viewer')
        return chapter_ids_under_folder(scope_id)
    # workspace: every chapter the current user can currently read at all --
    # whole-book access, plus narrower folder/chapter shares for books they
    # don't otherwise have whole-book access to (mirrors the old endpoint's
    # own set-building, and FolderPage/Sidebar's "shared with me" logic).
    book_ids = accessible_book_ids()
    chapter_ids = set()
    if book_ids:
        chapter_ids.update(row.id for row in Chapter.query.filter(Chapter.book_id.in_(book_ids)).with_entities(Chapter.id))
    shared_folders, shared_chapters = shared_items()
    for f in shared_folders:
        chapter_ids.update(chapter_ids_under_folder(f.id))
    for c in shared_chapters:
        chapter_ids.update(descendant_chapter_ids(c.id))
    return list(chapter_ids)


@api_bp.route('/search')
def api_search():
    query = (request.args.get('q') or '').strip()
    scope_type = request.args.get('scopeType') or 'workspace'
    if scope_type not in SEARCH_SCOPE_TYPES:
        return error('Invalid scopeType')

    raw_scope_id = request.args.get('scopeId')
    scope_id = None
    if scope_type in ('book', 'folder'):
        scope_id = parse_uuid(raw_scope_id)
        if scope_id is None:
            return error('scopeId is required and must be a valid UUID for this scopeType')
    elif raw_scope_id:
        return error('scopeId is not valid for a workspace search')

    try:
        limit = int(request.args.get('limit', SEARCH_DEFAULT_LIMIT))
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        return error('limit/offset must be integers')
    # Clamped, not rejected -- a caller asking for more than the max simply
    # gets the max back, so pathological limits can't force rendering (or
    # snippet-building, see below) thousands of results in one response.
    limit = max(1, min(limit, SEARCH_MAX_LIMIT))
    offset = max(0, offset)

    all_matches: list[tuple] = []
    matched_chapter_ids: set = set()
    if query:
        chapter_ids = _search_scope_chapter_ids(scope_type, scope_id)
        chapters = (
            Chapter.query.filter(Chapter.id.in_(chapter_ids))
            .order_by(Chapter.updated_at.desc(), Chapter.id)
            .all()
            if chapter_ids else []
        )
        # Every candidate chapter's title/content/notes must be scanned to
        # know the true total (unavoidable for a correct count/order with a
        # plain literal scan) -- but snippet text is only ever built below
        # for the one page actually being returned, not all totalMatches.
        for chapter in chapters:
            for m in search_chapter_matches(chapter, query):
                all_matches.append((chapter, m))
                matched_chapter_ids.add(chapter.id)

    total_matches = len(all_matches)
    total_chapters = len(matched_chapter_ids)
    page = all_matches[offset:offset + limit]

    book_ids_needed = {chapter.book_id for chapter, _ in page}
    books = (
        {row.id: row for row in Folder.query.filter(Folder.id.in_(book_ids_needed)).with_entities(Folder.id, Folder.name, Folder.color)}
        if book_ids_needed else {}
    )

    matches_out = []
    for chapter, m in page:
        book = books.get(chapter.book_id)
        matches_out.append({
            'chapterId': chapter.id,
            'chapterName': chapter.name,
            'bookId': chapter.book_id,
            'bookName': book.name if book is not None else '',
            'bookColor': (book.color or None) if book is not None else None,
            'source': m['source'],
            'occurrenceIndex': m['occurrenceIndex'],
            'startOffset': m['startOffset'],
            'endOffset': m['endOffset'],
            'snippet': build_search_snippet(m['text'], m['startOffset'], m['endOffset']),
        })

    return jsonify({
        'query': query,
        'scopeType': scope_type,
        'scopeId': scope_id,
        'totalMatches': total_matches,
        'totalChapters': total_chapters,
        'limit': limit,
        'offset': offset,
        'hasMore': offset + limit < total_matches,
        'matches': matches_out,
    })


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
