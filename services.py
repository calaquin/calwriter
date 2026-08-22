"""Shared data-layer logic used by the JSON API (api.py)."""
import calendar
import datetime
import json
import zipfile
from io import BytesIO

from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches
import bleach
from bleach.css_sanitizer import CSSSanitizer
from flask_login import current_user

from extensions import db
from models import UserSettings, Folder, Chapter, ChapterVersion, Goal, GoalType, GoalPeriodHistory
from permissions import accessible_book_ids

VERSION = "0.17.1"

CHAPTER_VERSION_MIN_INTERVAL = datetime.timedelta(minutes=5)
CHAPTER_VERSION_RETENTION = 50

STATS_STALE_GAP = datetime.timedelta(days=7)


def prune_words_per_day(words_per_day: dict) -> dict:
    """Drop zero-word days, which just mean nothing was last-touched that
    day rather than "0 words were written" -- except today, which stays
    even at 0 so the chart doesn't just stop looking alive. If today itself
    is 0 and it's been more than a week since the last day with any real
    words (or there's never been one), drop today too, rather than show a
    lone empty bar stranded past a long gap of inactivity."""
    real_days = sorted(d for d, c in words_per_day.items() if c > 0)
    pruned = {d: words_per_day[d] for d in real_days}

    today = datetime.date.today()
    today_iso = today.isoformat()
    if today_iso not in words_per_day or words_per_day[today_iso] > 0:
        return pruned
    if real_days and today - datetime.date.fromisoformat(real_days[-1]) <= STATS_STALE_GAP:
        pruned[today_iso] = words_per_day[today_iso]
    return pruned


def clean_name(name: str) -> str:
    """Light cosmetic cleanup for a user-supplied name (no filesystem safety needed --
    names are DB values matched by exact string, never used to build a path)."""
    return name.strip()[:255]


def _to_alpha(n: int) -> str:
    """1 -> a, 2 -> b, ..., 26 -> z, 27 -> aa, ... (bijective base-26)."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(97 + r) + s
    return s


def _to_roman(n: int) -> str:
    vals = [
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
        (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
    ]
    s = ""
    for value, symbol in vals:
        count, n = divmod(n, value)
        s += symbol * count
    return s


_ORDERED_MARKERS = [lambda n: f"{n}.", lambda n: f"{_to_alpha(n)}.", lambda n: f"{_to_roman(n)}."]
_UNORDERED_MARKERS = ["•", "◦", "▪"]  # •, ◦, ▪


def _list_marker(depth: int, ordered: bool, index: int, checked) -> str:
    """The prefix for one list item -- cycles decimal/alpha/roman (ordered)
    or disc/circle/square (unordered) every 3 nesting levels, matching the
    editor's CSS, or a checkbox glyph for a checklist item regardless of
    ordered/unordered (checklists are always rendered as a plain ul)."""
    if checked is not None:
        return "[x]" if checked else "[ ]"
    if ordered:
        return _ORDERED_MARKERS[depth % 3](index)
    return _UNORDERED_MARKERS[depth % 3]


def _walk_list(list_elem, depth=0):
    """Yield (depth, ordered, index, checked, own_children) for every <li>
    under list_elem, in document order, recursing into a nested <ul>/<ol>
    right after its parent <li>'s own content (own_children excludes any
    nested list, which is walked separately by the recursive call). index is
    1-based and resets within each nested list. Each consumer picks its own
    marker convention from these fields -- e.g. depth-cycling glyphs for
    docx/rtf/txt (mirroring the editor's own display), vs. markdown's flat
    "-"/"N." convention where indentation alone conveys nesting."""
    ordered = list_elem.name == "ol"
    index = 0
    for li in list_elem.find_all("li", recursive=False):
        index += 1
        classes = li.get("class") or []
        checked = ("checked" in classes) if "checklist-item" in classes else None
        own_children = [c for c in li.children if getattr(c, "name", None) not in ("ul", "ol")]
        yield depth, ordered, index, checked, own_children
        for nested in li.find_all(["ul", "ol"], recursive=False):
            yield from _walk_list(nested, depth + 1)


def html_to_text(html: str) -> str:
    """Convert HTML to plain text, with list items prefixed by their marker
    (bullet/number/checkbox) and indented by nesting depth -- otherwise a
    list is indistinguishable from a run of separate paragraphs."""
    soup = BeautifulSoup(html, "html.parser")

    def block_text(elem) -> str:
        if elem.name in ("ul", "ol"):
            lines = [
                f"{'  ' * depth}{_list_marker(depth, ordered, index, checked)} "
                f"{''.join(c.get_text() for c in own).strip()}"
                for depth, ordered, index, checked, own in _walk_list(elem)
            ]
            return "\n".join(lines)
        return elem.get_text(separator="\n")

    parts = []
    for elem in soup.children:
        text = (elem if isinstance(elem, str) else block_text(elem)).strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


_CSS_SANITIZER = CSSSanitizer(allowed_css_properties=["text-indent", "text-align"])


def sanitize_html(html: str) -> str:
    """Strip unwanted tags to prevent script injection. A CSSSanitizer is
    required here -- without one, bleach silently drops the *entire* style
    attribute (not just disallowed properties) even though "style" is listed
    as an allowed attribute below, which was quietly discarding the editor's
    first-line-indent and text-align formatting on every save."""
    allowed_tags = [
        "b", "strong", "i", "em", "u", "p", "br", "div", "ul", "ol", "li", "hr",
        "span", "img"
    ]
    allowed_attrs = {
        "*": ["class", "style"],
        "img": ["src", "alt", "width", "height", "style"]
    }
    return bleach.clean(
        html, tags=allowed_tags, attributes=allowed_attrs, css_sanitizer=_CSS_SANITIZER, strip=True
    )


def append_html_to_docx(doc: Document, html: str) -> None:
    """Append limited HTML content to a DOCX document."""
    soup = BeautifulSoup(html, "html.parser")

    def process(elem, paragraph, formatting=None):
        if formatting is None:
            formatting = {}
        if isinstance(elem, str):
            run = paragraph.add_run(elem)
            run.bold = formatting.get("bold", False)
            run.italic = formatting.get("italic", False)
            run.underline = formatting.get("underline", False)
            return
        tag = elem.name
        fmt = formatting.copy()
        if tag in ("strong", "b"):
            fmt["bold"] = True
        if tag in ("em", "i"):
            fmt["italic"] = True
        if tag == "u":
            fmt["underline"] = True
        if tag == "img":
            src = elem.get("src", "")
            if src.startswith("data:image/"):
                import base64
                header, b64 = src.split(",", 1)
                data = base64.b64decode(b64)
                bio = BytesIO(data)
                width = elem.get("width")
                height = elem.get("height")
                w = Inches(int(width) / 96) if width and width.isdigit() else None
                h = Inches(int(height) / 96) if height and height.isdigit() else None
                doc.add_picture(bio, width=w, height=h)
            return
        if tag in ("p", "div", "br"):
            p = doc.add_paragraph()
            p.paragraph_format.first_line_indent = Inches(0.5)
            for child in elem.children:
                process(child, p, fmt)
            return
        if tag in ("ul", "ol"):
            for depth, ordered, index, checked, own in _walk_list(elem):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.25 * (depth + 1))
                p.add_run(f"{_list_marker(depth, ordered, index, checked)}  ")
                for child in own:
                    process(child, p, fmt)
            return
        for child in elem.children:
            process(child, paragraph, fmt)

    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Inches(0.5)
    for child in soup.children:
        process(child, p)


def render_chapter_docx(content_html: str) -> Document:
    doc = Document()
    append_html_to_docx(doc, content_html)
    return doc


def render_book_docx(chapters: list) -> Document:
    doc = Document()
    for idx, chapter in enumerate(chapters):
        doc.add_heading(chapter.name, level=1)
        append_html_to_docx(doc, chapter.content_html)
        if idx < len(chapters) - 1:
            doc.add_page_break()
    return doc


def html_to_markdown(html: str) -> str:
    """Convert the editor's limited HTML dialect to Markdown. Alignment/indent
    styling has no plain-Markdown equivalent and is dropped, same as .txt."""
    soup = BeautifulSoup(html, "html.parser")

    def render_inline(elem) -> str:
        if isinstance(elem, str):
            return elem
        tag = elem.name
        inner = "".join(render_inline(c) for c in elem.children)
        if tag in ("strong", "b"):
            return f"**{inner}**" if inner.strip() else inner
        if tag in ("em", "i"):
            return f"*{inner}*" if inner.strip() else inner
        if tag == "u":
            return f"<u>{inner}</u>" if inner.strip() else inner
        if tag == "br":
            return "  \n"
        return inner

    def render_children(children) -> str:
        return "".join(render_inline(c) for c in children)

    blocks = []
    for elem in soup.children:
        if isinstance(elem, str):
            text = elem.strip()
            if text:
                blocks.append(text)
            continue
        tag = elem.name
        if tag == "hr":
            blocks.append("---")
        elif tag in ("ul", "ol"):
            items = []
            for depth, ordered, index, checked, own in _walk_list(elem):
                if checked is not None:
                    prefix = "- [x]" if checked else "- [ ]"
                elif ordered:
                    prefix = f"{index}."
                else:
                    prefix = "-"
                items.append(f"{'  ' * depth}{prefix} {render_children(own).strip()}")
            blocks.append("\n".join(items))
        else:
            text = render_inline(elem).strip()
            if text:
                blocks.append(text)
    return "\n\n".join(blocks)


def _rtf_escape(text: str) -> str:
    text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return "".join(ch if ord(ch) < 128 else f"\\u{ord(ch)}?" for ch in text)


def html_to_rtf_body(html: str) -> str:
    """RTF content fragment for one chapter's HTML, without the document
    header/footer -- render_chapter_rtf / render_folder_rtf wrap this."""
    soup = BeautifulSoup(html, "html.parser")

    def render(elem) -> str:
        if isinstance(elem, str):
            return _rtf_escape(elem)
        tag = elem.name
        if tag == "br":
            return "\\line "
        if tag == "hr":
            return "\\line \\emdash\\emdash\\emdash\\emdash\\emdash\\line "
        if tag in ("ul", "ol"):
            parts = []
            for depth, ordered, index, checked, own in _walk_list(elem):
                marker = _rtf_escape(_list_marker(depth, ordered, index, checked))
                indent = 360 * (depth + 1)
                inner = "".join(render(c) for c in own)
                parts.append(f"\\li{indent} {marker}\\tab {inner}\\par ")
            return "".join(parts) + "\\li0 "
        inner = "".join(render(c) for c in elem.children)
        if tag in ("strong", "b"):
            return f"\\b {inner}\\b0 "
        if tag in ("em", "i"):
            return f"\\i {inner}\\i0 "
        if tag == "u":
            return f"\\ul {inner}\\ulnone "
        if tag in ("p", "div"):
            return f"{inner}\\par "
        return inner

    return "".join(render(c) for c in soup.children)


def render_chapter_rtf(content_html: str) -> bytes:
    body = html_to_rtf_body(content_html)
    return ("{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Calibri;}}\\f0\\fs24 " + body + "}").encode("utf-8")


def render_folder_rtf(folder_name: str, chapters: list) -> bytes:
    parts = [f"{{\\b\\fs36 {_rtf_escape(folder_name)}\\par}}\\par "]
    for chapter in chapters:
        parts.append(f"{{\\b\\fs28 {_rtf_escape(chapter.name)}\\par}}")
        parts.append(html_to_rtf_body(chapter.content_html))
        parts.append("\\par ")
    body = "".join(parts)
    return ("{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Calibri;}}\\f0\\fs24 " + body + "}").encode("utf-8")


def render_folder_markdown(folder_name: str, chapters: list) -> str:
    parts = [f"# {folder_name}"]
    for chapter in chapters:
        parts.append(f"## {chapter.name}\n\n{html_to_markdown(chapter.content_html)}")
    return "\n\n".join(parts)


def render_folder_txt(folder_name: str, chapters: list) -> str:
    parts = [folder_name]
    for chapter in chapters:
        parts.append(f"{chapter.name}\n\n{html_to_text(chapter.content_html)}")
    return "\n\n\n".join(parts)


def render_folder_docx(folder_name: str, chapters: list) -> Document:
    doc = Document()
    doc.add_heading(folder_name, level=0)
    for idx, chapter in enumerate(chapters):
        doc.add_heading(chapter.name, level=1)
        append_html_to_docx(doc, chapter.content_html)
        if idx < len(chapters) - 1:
            doc.add_page_break()
    return doc


def folder_chapters_recursive(folder_id: int) -> list:
    """All chapters in a folder and its descendants (including nested
    sub-folders), in a stable read order."""
    folder_ids = descendant_folder_ids(folder_id)
    return (
        Chapter.query.filter(Chapter.folder_id.in_(folder_ids))
        .order_by(Chapter.position, Chapter.created_at)
        .all()
    )


def get_user_settings() -> UserSettings:
    settings = db.session.get(UserSettings, current_user.id)
    if settings is None:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    return settings


def descendant_folder_ids(root_folder_id: int) -> list:
    ids = [root_folder_id]
    frontier = [root_folder_id]
    while frontier:
        children = Folder.query.filter(Folder.parent_id.in_(frontier)).with_entities(Folder.id).all()
        frontier = [c.id for c in children]
        ids.extend(frontier)
    return ids


def resource_word_count(folder: Folder | None = None, chapter: Chapter | None = None) -> int:
    """Total word count for a goal's target resource -- a single chapter, or
    a folder's entire descendant subtree. Same shape as the per-chapter
    counting already done in the folder/chapter/workspace stats endpoints,
    factored out here so goal progress uses the identical logic."""
    if chapter is not None:
        return len(html_to_text(chapter.content_html).split())
    if folder is not None:
        folder_ids = descendant_folder_ids(folder.id)
        chapters = Chapter.query.filter(Chapter.folder_id.in_(folder_ids)).all()
        return sum(len(html_to_text(c.content_html).split()) for c in chapters)
    return 0


def resource_completed_chapter_count(folder: Folder, period_start: datetime.date) -> int:
    """Chapters under `folder` (including nested sub-folders) marked
    complete on or after `period_start` -- a chapter completed long before
    the goal's current period doesn't count toward it."""
    folder_ids = descendant_folder_ids(folder.id)
    cutoff = datetime.datetime.combine(period_start, datetime.time.min, tzinfo=datetime.timezone.utc)
    return Chapter.query.filter(
        Chapter.folder_id.in_(folder_ids),
        Chapter.completed_at.isnot(None),
        Chapter.completed_at >= cutoff,
    ).count()


def _goal_period_final_current(goal: Goal, period_start: datetime.date, period_end: datetime.date) -> int:
    """Final progress value for one already-elapsed period, for its
    GoalPeriodHistory row. Unlike the live progress shown for the *current*
    period (which has no upper bound -- "now" is the bound), a past
    period's count is capped at its own end so it doesn't pick up activity
    from periods after it."""
    if goal.goal_type == GoalType.words:
        # The only baseline available is the one captured for period_start;
        # if it was never captured (this period was skipped over without
        # ever being the *current* one -- e.g. the goal wasn't read again
        # until several periods later), there's nothing honest to report.
        if goal.baseline_word_count is None:
            return 0
        return max(0, resource_word_count(folder=goal.folder, chapter=goal.chapter) - goal.baseline_word_count)
    folder_ids = descendant_folder_ids(goal.folder_id)
    cutoff_start = datetime.datetime.combine(period_start, datetime.time.min, tzinfo=datetime.timezone.utc)
    cutoff_end = datetime.datetime.combine(period_end, datetime.time.max, tzinfo=datetime.timezone.utc)
    return Chapter.query.filter(
        Chapter.folder_id.in_(folder_ids),
        Chapter.completed_at.isnot(None),
        Chapter.completed_at >= cutoff_start,
        Chapter.completed_at <= cutoff_end,
    ).count()


def advance_date_by_cadence(period_start: datetime.date, cadence: str) -> datetime.date:
    if cadence == 'daily':
        return period_start + datetime.timedelta(days=1)
    if cadence == 'weekly':
        return period_start + datetime.timedelta(days=7)
    if cadence == 'monthly':
        year = period_start.year + period_start.month // 12
        month = period_start.month % 12 + 1
        day = min(period_start.day, calendar.monthrange(year, month)[1])
        return datetime.date(year, month, day)
    raise ValueError(f'Unknown cadence: {cadence}')


def advance_goal_period(goal: Goal) -> None:
    """Lazily roll a recurring goal's period forward past any boundaries
    that have already elapsed, and (re)capture its word-count baseline the
    first time it's observed on/after the (possibly just-rolled) period
    start. Called on every read of a goal (see api.api_list_goals) --
    idempotent, mutates `goal` in place, caller is responsible for
    committing. A fixed-range goal (cadence is None) never rolls; its
    baseline is captured exactly once, whenever start_date first arrives.
    A recurring goal with an end_date stops rolling once that date has
    passed, freezing it at its last active period -- same "captured once,
    stays put" shape as a fixed-range goal from that point on.

    Every period actually rolled past here is *the* one chance to record it
    into GoalPeriodHistory -- once period_start moves on, the old period's
    baseline is gone. Only the first one gets a row: if several periods
    elapsed unread (e.g. a month idle on a daily goal), the ones after the
    first were never individually observed, so a real per-period number
    for them doesn't exist -- recording zeroes would misrepresent a gap
    in visits as a gap in writing."""
    today = datetime.date.today()
    rolled = False
    if goal.cadence is not None and (goal.end_date is None or today <= goal.end_date):
        first_rollover = True
        while today >= advance_date_by_cadence(goal.period_start, goal.cadence.value):
            next_period_start = advance_date_by_cadence(goal.period_start, goal.cadence.value)
            if first_rollover:
                period_end = next_period_start - datetime.timedelta(days=1)
                current = _goal_period_final_current(goal, goal.period_start, period_end)
                db.session.add(GoalPeriodHistory(
                    goal_id=goal.id,
                    period_start=goal.period_start,
                    period_end=period_end,
                    target=goal.target,
                    current=current,
                    achieved=current >= goal.target,
                ))
                first_rollover = False
            goal.period_start = next_period_start
            rolled = True
    if goal.goal_type == GoalType.words and today >= goal.period_start and (rolled or goal.baseline_word_count is None):
        goal.baseline_word_count = resource_word_count(folder=goal.folder, chapter=goal.chapter)


def next_folder_position(parent_id) -> int:
    q = db.session.query(db.func.max(Folder.position))
    q = q.filter(Folder.parent_id.is_(None)) if parent_id is None else q.filter(Folder.parent_id == parent_id)
    return (q.scalar() or -1) + 1


def next_chapter_position(folder_id: int) -> int:
    max_pos = db.session.query(db.func.max(Chapter.position)).filter(Chapter.folder_id == folder_id).scalar()
    return (max_pos or -1) + 1


def snapshot_chapter_version(chapter: Chapter, *, force: bool = False) -> None:
    """Write a ChapterVersion checkpoint capturing the chapter's CURRENT
    content_html, before the caller overwrites it. Skipped unless `force` or
    the last snapshot for this chapter is older than CHAPTER_VERSION_MIN_INTERVAL,
    so continuous autosave doesn't create a row per keystroke pause. Prunes
    down to the most recent CHAPTER_VERSION_RETENTION rows afterward."""
    if not force:
        latest = (
            ChapterVersion.query.filter_by(chapter_id=chapter.id)
            .order_by(ChapterVersion.created_at.desc())
            .first()
        )
        if latest is not None:
            now = datetime.datetime.now(datetime.timezone.utc)
            latest_created_at = latest.created_at
            if latest_created_at.tzinfo is None:
                latest_created_at = latest_created_at.replace(tzinfo=datetime.timezone.utc)
            if now - latest_created_at < CHAPTER_VERSION_MIN_INTERVAL:
                return
    db.session.add(ChapterVersion(chapter_id=chapter.id, content_html=chapter.content_html))
    db.session.flush()
    stale_ids = [
        v.id
        for v in ChapterVersion.query.filter_by(chapter_id=chapter.id)
        .order_by(ChapterVersion.created_at.desc())
        .offset(CHAPTER_VERSION_RETENTION)
        .all()
    ]
    if stale_ids:
        ChapterVersion.query.filter(ChapterVersion.id.in_(stale_ids)).delete(synchronize_session=False)


def create_book(name: str, owner_id: int, description: str = '', author: str = '', color: str = '') -> Folder:
    """Insert a new top-level book. book_id is self-referential (NOT NULL FK to
    folders.id), so pre-fetch the id from the sequence and insert id == book_id
    together in one statement -- Postgres checks FK constraints post-statement,
    so a row referencing itself in a single INSERT is valid."""
    new_id = db.session.execute(db.text("SELECT nextval('folders_id_seq')")).scalar()
    folder = Folder(
        id=new_id,
        book_id=new_id,
        parent_id=None,
        owner_id=owner_id,
        name=name,
        description=description,
        author=author,
        color=color,
    )
    db.session.add(folder)
    db.session.flush()
    return folder


def ordered_accessible_books() -> list:
    ids = accessible_book_ids()
    if not ids:
        return []
    books = Folder.query.filter(Folder.id.in_(ids)).all()
    order = get_user_settings().book_order
    by_id = {b.id: b for b in books}
    ordered = [by_id[i] for i in order if i in by_id]
    seen = set(order)
    remaining = sorted((b for b in books if b.id not in seen), key=lambda b: b.created_at)
    return ordered + remaining


def serialize_folder(folder: Folder) -> dict:
    subfolders = Folder.query.filter_by(parent_id=folder.id).order_by(Folder.position, Folder.created_at).all()
    chapters = Chapter.query.filter_by(folder_id=folder.id).order_by(Chapter.position, Chapter.created_at).all()
    return {
        'name': folder.name,
        'description': folder.description,
        'author': folder.author,
        'color': folder.color,
        'folders': [serialize_folder(s) for s in subfolders],
        'chapters': [
            {
                'name': c.name,
                'description': c.description,
                'content_html': c.content_html,
                'notes_text': c.notes_text,
            }
            for c in chapters
        ],
    }


def export_books_zip() -> BytesIO:
    """Zipped JSON dump of the current user's accessible books (owned + shared)."""
    books = ordered_accessible_books()
    payload = {
        'version': '2.0',
        'exported_at': datetime.datetime.utcnow().isoformat(),
        'exported_by': current_user.username,
        'books': [serialize_folder(b) for b in books],
    }
    mem = BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('data.json', json.dumps(payload))
    mem.seek(0)
    return mem


def deserialize_folder(data: dict, parent: Folder, book_id: int, position: int) -> Folder:
    folder = Folder(
        parent_id=parent.id,
        book_id=book_id,
        name=clean_name(data.get('name', 'Untitled')) or 'Untitled',
        description=data.get('description', ''),
        author=data.get('author', ''),
        color=data.get('color', ''),
        position=position,
    )
    db.session.add(folder)
    db.session.flush()
    for idx, sub in enumerate(data.get('folders', [])):
        deserialize_folder(sub, folder, book_id, idx)
    for idx, chap in enumerate(data.get('chapters', [])):
        db.session.add(Chapter(
            folder_id=folder.id,
            book_id=book_id,
            name=clean_name(chap.get('name', 'Untitled')) or 'Untitled',
            description=chap.get('description', ''),
            content_html=sanitize_html(chap.get('content_html', '')),
            notes_text=chap.get('notes_text', ''),
            position=idx,
        ))
    return folder


def import_books_zip(file_storage, owner_id: int) -> int:
    """Import a .calwdb archive. Always creates new books owned by owner_id --
    never merges/overwrites existing books by name. Returns count imported.
    Raises ValueError on invalid archive contents (caller decides how to report)."""
    try:
        with zipfile.ZipFile(file_storage) as zf:
            if 'data.json' not in zf.namelist():
                raise ValueError('Archive is missing data.json')
            payload = json.loads(zf.read('data.json'))
    except zipfile.BadZipFile:
        raise ValueError('File is not a valid archive')
    except json.JSONDecodeError:
        raise ValueError('Archive contents are invalid')

    settings = get_user_settings()
    books_data = payload.get('books', [])
    for book_data in books_data:
        name = clean_name(book_data.get('name', 'Untitled')) or 'Untitled'
        base_name, suffix = name, 1
        while Folder.query.filter_by(parent_id=None, name=name).first():
            suffix += 1
            name = f"{base_name} ({suffix})"
        book = create_book(
            name,
            owner_id=owner_id,
            description=book_data.get('description', ''),
            author=book_data.get('author', ''),
            color=book_data.get('color', ''),
        )
        for idx, sub in enumerate(book_data.get('folders', [])):
            deserialize_folder(sub, book, book.id, idx)
        for idx, chap in enumerate(book_data.get('chapters', [])):
            db.session.add(Chapter(
                folder_id=book.id,
                book_id=book.id,
                name=clean_name(chap.get('name', 'Untitled')) or 'Untitled',
                description=chap.get('description', ''),
                content_html=sanitize_html(chap.get('content_html', '')),
                notes_text=chap.get('notes_text', ''),
                position=idx,
            ))
        if book.id not in settings.open_book_ids:
            settings.open_book_ids = settings.open_book_ids + [book.id]
    db.session.commit()
    return len(books_data)
