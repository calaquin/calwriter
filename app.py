import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import re
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches

app = Flask(__name__)
app.secret_key = 'change-this'

DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.getcwd(), 'data'))

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)


def safe_name(name: str) -> str:
    return ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-')).rstrip()


def html_to_text(html: str) -> str:
    """Convert HTML to plain text."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n")


def html_to_docx(html: str, path: str) -> None:
    """Save limited HTML content to a DOCX file."""
    doc = Document()
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
    doc.save(path)


def sanitize_path(folder: str) -> str:
    parts = [safe_name(p) for p in folder.split('/') if p]
    return os.path.join(*parts) if parts else ''


def list_chapters(folder: str):
    path = os.path.join(DATA_DIR, sanitize_path(folder))
    if os.path.isdir(path):
        chapters = [
            c
            for c in os.listdir(path)
            if os.path.isdir(os.path.join(path, c))
            and os.path.isfile(os.path.join(path, c, 'chapter.html'))
        ]
        chapters.sort(key=lambda n: os.path.getctime(os.path.join(path, n)))
        return chapters
    return []


def list_subfolders(folder: str):
    path = os.path.join(DATA_DIR, sanitize_path(folder))
    if os.path.isdir(path):
        subs = [
            c
            for c in os.listdir(path)
            if os.path.isdir(os.path.join(path, c))
            and not os.path.isfile(os.path.join(path, c, 'chapter.html'))
        ]
        subs.sort(key=lambda n: os.path.getctime(os.path.join(path, n)))
        return subs
    return []


def note_filename(chapter: str) -> str:
    """Return the standard notes filename for a chapter."""
    return f"{chapter.replace(' ', '_')}_notes.txt"


def list_notes(folder: str, chapter: str):
    """Return the notes filename for the chapter if it exists."""
    path = os.path.join(DATA_DIR, sanitize_path(folder), safe_name(chapter))
    filename = note_filename(chapter)
    note_path = os.path.join(path, filename)
    if os.path.isfile(note_path):
        return [filename]
    return []


app.jinja_env.globals['list_chapters'] = list_chapters
app.jinja_env.globals['list_notes'] = list_notes
app.jinja_env.globals['list_subfolders'] = list_subfolders


@app.route('/')
def index():
    folders = [f for f in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, f))]
    folders.sort(key=lambda n: os.path.getctime(os.path.join(DATA_DIR, n)))
    return render_template('index.html', folders=folders)


@app.route('/folder/create', methods=['POST'])
def create_folder():
    name = safe_name(request.form.get('name', ''))
    if not name:
        flash('Folder name required')
        return redirect(url_for('index'))
    path = os.path.join(DATA_DIR, name)
    os.makedirs(path, exist_ok=True)
    return redirect(url_for('view_folder', folder=name))


@app.route('/folder/<path:folder>/delete', methods=['POST'])
def delete_folder(folder):
    folder_name = sanitize_path(folder)
    path = os.path.join(DATA_DIR, folder_name)
    if os.path.isdir(path):
        import shutil
        shutil.rmtree(path)
        flash('Book deleted')
    else:
        flash('Book not found')
    parent = os.path.dirname(folder_name)
    if parent:
        return redirect(url_for('view_folder', folder=parent))
    return redirect(url_for('index'))


@app.route('/folder/<path:folder>')
def view_folder(folder):
    folder_name = sanitize_path(folder)
    path = os.path.join(DATA_DIR, folder_name)
    if not os.path.isdir(path):
        flash('Folder not found')
        return redirect(url_for('index'))
    chapters = list_chapters(folder_name)
    subfolders = list_subfolders(folder_name)
    folders = [f for f in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, f))]
    folders.sort(key=lambda n: os.path.getctime(os.path.join(DATA_DIR, n)))
    return render_template('folder.html', folder=folder_name, chapters=chapters, subfolders=subfolders, folders=folders)


@app.route('/folder/<path:folder>/chapter/create', methods=['POST'])
def create_chapter(folder):
    folder_name = sanitize_path(folder)
    chapter = safe_name(request.form.get('name', ''))
    if not chapter:
        flash('Chapter name required')
        return redirect(url_for('view_folder', folder=folder_name))
    path = os.path.join(DATA_DIR, folder_name, chapter)
    os.makedirs(path, exist_ok=True)
    open(os.path.join(path, 'chapter.html'), 'a').close()
    return redirect(url_for('view_chapter', folder=folder_name, chapter=chapter))


@app.route('/folder/<path:folder>/<chapter>')
def view_chapter(folder, chapter):
    folder_name = sanitize_path(folder)
    chapter_name = safe_name(chapter)
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    if not os.path.isdir(path):
        flash('Chapter not found')
        return redirect(url_for('view_folder', folder=folder_name))
    chapter_file = os.path.join(path, 'chapter.html')
    chapter_html = ''
    if os.path.isfile(chapter_file):
        with open(chapter_file) as f:
            chapter_html = f.read()

    notes_file = os.path.join(path, note_filename(chapter_name))
    notes_text = ''
    if os.path.isfile(notes_file):
        with open(notes_file) as f:
            notes_text = f.read()

    folders = [f for f in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, f))]
    folders.sort(key=lambda n: os.path.getctime(os.path.join(DATA_DIR, n)))
    chapters = list_chapters(folder_name)
    return render_template(
        'chapter.html',
        folder=folder_name,
        chapter=chapter_name,
        notes_text=notes_text,
        folders=folders,
        chapters=chapters,
        chapter_html=chapter_html
    )



@app.route('/folder/<path:folder>/<chapter>/notes/save', methods=['POST'])
def save_notes(folder, chapter):
    folder_name = sanitize_path(folder)
    chapter_name = safe_name(chapter)
    text = request.form.get('notes', '')
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    os.makedirs(path, exist_ok=True)
    note_path = os.path.join(path, note_filename(chapter_name))
    with open(note_path, 'w') as f:
        f.write(text)
    return ('', 204)


@app.route('/folder/<path:folder>/<chapter>/save', methods=['POST'])
def save_chapter(folder, chapter):
    folder_name = sanitize_path(folder)
    chapter_name = safe_name(chapter)
    text = request.form.get('text', '')
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    os.makedirs(path, exist_ok=True)
    html_path = os.path.join(path, 'chapter.html')
    with open(html_path, 'w') as f:
        f.write(text)
    docx_path = os.path.join(path, 'chapter.docx')
    html_to_docx(text, docx_path)
    return redirect(url_for('view_chapter', folder=folder_name, chapter=chapter_name))


@app.route('/folder/<path:folder>/<chapter>/autosave', methods=['POST'])
def autosave_chapter(folder, chapter):
    folder_name = sanitize_path(folder)
    chapter_name = safe_name(chapter)
    text = request.form.get('text', '')
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    os.makedirs(path, exist_ok=True)
    html_path = os.path.join(path, 'chapter.html')
    with open(html_path, 'w') as f:
        f.write(text)
    docx_path = os.path.join(path, 'chapter.docx')
    html_to_docx(text, docx_path)
    return ('', 204)


@app.route('/folder/<path:folder>/<chapter>/delete', methods=['POST'])
def delete_chapter(folder, chapter):
    folder_name = sanitize_path(folder)
    chapter_name = safe_name(chapter)
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    if os.path.isdir(path):
        import shutil
        shutil.rmtree(path)
        flash('Chapter deleted')
    else:
        flash('Chapter not found')
    return redirect(url_for('view_folder', folder=folder_name))


@app.route('/folder/<path:folder>/<chapter>/notes/download')
def download_note(folder, chapter):
    folder_name = sanitize_path(folder)
    chapter_name = safe_name(chapter)
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    note_name = note_filename(chapter_name)
    return send_from_directory(path, note_name, as_attachment=True, download_name=note_name)


@app.route('/folder/<path:folder>/<chapter>/chapter.docx')
def download_chapter_docx(folder, chapter):
    folder_name = sanitize_path(folder)
    chapter_name = safe_name(chapter)
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    return send_from_directory(
        path,
        'chapter.docx',
        as_attachment=True,
        download_name=f"{chapter_name}.docx",
    )


@app.route('/folder/<path:folder>/folder/create', methods=['POST'])
def create_subfolder(folder):
    folder_name = sanitize_path(folder)
    name = safe_name(request.form.get('name', ''))
    if not name:
        flash('Folder name required')
        return redirect(url_for('view_folder', folder=folder_name))
    path = os.path.join(DATA_DIR, folder_name, name)
    os.makedirs(path, exist_ok=True)
    return redirect(url_for('view_folder', folder=f"{folder_name}/{name}"))


@app.route('/folder/<path:folder>/stats')
def folder_stats(folder):
    folder_name = sanitize_path(folder)
    path = os.path.join(DATA_DIR, folder_name)
    total_words = 0
    words_per_day = {}
    for root, dirs, files in os.walk(path):
        if 'chapter.html' in files:
            html_path = os.path.join(root, 'chapter.html')
            with open(html_path) as f:
                text = html_to_text(f.read())
            count = len(text.split())
            total_words += count
            day = datetime.date.fromtimestamp(os.path.getmtime(html_path)).isoformat()
            words_per_day[day] = words_per_day.get(day, 0) + count
    folders = [f for f in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, f))]
    folders.sort(key=lambda n: os.path.getctime(os.path.join(DATA_DIR, n)))
    return render_template('stats.html', folder=folder_name, total_words=total_words, words_per_day=words_per_day, folders=folders)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
