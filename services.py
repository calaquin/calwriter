"""Shared data-layer logic used by the JSON API (api.py)."""
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
from models import UserSettings, Folder, Chapter, ChapterVersion
from permissions import accessible_book_ids

VERSION = "0.13.0"

CHAPTER_VERSION_MIN_INTERVAL = datetime.timedelta(minutes=5)
CHAPTER_VERSION_RETENTION = 50


def clean_name(name: str) -> str:
    """Light cosmetic cleanup for a user-supplied name (no filesystem safety needed --
    names are DB values matched by exact string, never used to build a path)."""
    return name.strip()[:255]


def html_to_text(html: str) -> str:
    """Convert HTML to plain text."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n")


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
            for idx, li in enumerate(elem.find_all("li", recursive=False), start=1):
                prefix = f"{idx}." if tag == "ol" else "-"
                items.append(f"{prefix} {render_inline(li).strip()}")
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
        inner = "".join(render(c) for c in elem.children)
        if tag in ("strong", "b"):
            return f"\\b {inner}\\b0 "
        if tag in ("em", "i"):
            return f"\\i {inner}\\i0 "
        if tag == "u":
            return f"\\ul {inner}\\ulnone "
        if tag == "li":
            return f"\\bullet  {inner}\\par "
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
