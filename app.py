import os
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


def list_chapters(folder: str):
    path = os.path.join(DATA_DIR, folder)
    if os.path.isdir(path):
        chapters = [c for c in os.listdir(path) if os.path.isdir(os.path.join(path, c))]
        chapters.sort(key=lambda n: os.path.getctime(os.path.join(path, n)))
        return chapters
    return []


def list_notes(folder: str, chapter: str):
    path = os.path.join(DATA_DIR, folder, chapter)
    if os.path.isdir(path):
        notes = [n for n in os.listdir(path) if n.endswith('.txt')]
        notes.sort(key=lambda n: os.path.getctime(os.path.join(path, n)))
        return notes
    return []


app.jinja_env.globals['list_chapters'] = list_chapters
app.jinja_env.globals['list_notes'] = list_notes


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


@app.route('/folder/<folder>')
def view_folder(folder):
    folder_name = safe_name(folder)
    path = os.path.join(DATA_DIR, folder_name)
    if not os.path.isdir(path):
        flash('Folder not found')
        return redirect(url_for('index'))
    chapters = [c for c in os.listdir(path) if os.path.isdir(os.path.join(path, c))]
    chapters.sort(key=lambda n: os.path.getctime(os.path.join(path, n)))
    folders = [f for f in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, f))]
    folders.sort(key=lambda n: os.path.getctime(os.path.join(DATA_DIR, n)))
    return render_template('folder.html', folder=folder_name, chapters=chapters, folders=folders)


@app.route('/folder/<folder>/chapter/create', methods=['POST'])
def create_chapter(folder):
    folder_name = safe_name(folder)
    chapter = safe_name(request.form.get('name', ''))
    if not chapter:
        flash('Chapter name required')
        return redirect(url_for('view_folder', folder=folder_name))
    path = os.path.join(DATA_DIR, folder_name, chapter)
    os.makedirs(path, exist_ok=True)
    return redirect(url_for('view_chapter', folder=folder_name, chapter=chapter))


@app.route('/folder/<folder>/<chapter>')
def view_chapter(folder, chapter):
    folder_name = safe_name(folder)
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
    notes = [n for n in os.listdir(path) if n.endswith('.txt')]
    notes.sort(key=lambda n: os.path.getctime(os.path.join(path, n)))
    folders = [f for f in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, f))]
    folders.sort(key=lambda n: os.path.getctime(os.path.join(DATA_DIR, n)))
    chapters = [c for c in os.listdir(os.path.join(DATA_DIR, folder_name)) if os.path.isdir(os.path.join(DATA_DIR, folder_name, c))]
    chapters.sort(key=lambda n: os.path.getctime(os.path.join(DATA_DIR, folder_name, n)))
    return render_template(
        'chapter.html',
        folder=folder_name,
        chapter=chapter_name,
        notes=notes,
        folders=folders,
        chapters=chapters,
        chapter_html=chapter_html
    )


@app.route('/folder/<folder>/<chapter>/note/create', methods=['POST'])
def create_note(folder, chapter):
    folder_name = safe_name(folder)
    chapter_name = safe_name(chapter)
    title = safe_name(request.form.get('title', ''))
    text = request.form.get('text', '')
    if not title:
        flash('Note title required')
        return redirect(url_for('view_chapter', folder=folder_name, chapter=chapter_name))
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    os.makedirs(path, exist_ok=True)
    note_path = os.path.join(path, f"{title}.txt")
    with open(note_path, 'w') as f:
        f.write(html_to_text(text))
    return redirect(url_for('view_chapter', folder=folder_name, chapter=chapter_name))


@app.route('/folder/<folder>/<chapter>/save', methods=['POST'])
def save_chapter(folder, chapter):
    folder_name = safe_name(folder)
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


@app.route('/folder/<folder>/<chapter>/delete', methods=['POST'])
def delete_chapter(folder, chapter):
    folder_name = safe_name(folder)
    chapter_name = safe_name(chapter)
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    if os.path.isdir(path):
        import shutil
        shutil.rmtree(path)
        flash('Chapter deleted')
    else:
        flash('Chapter not found')
    return redirect(url_for('view_folder', folder=folder_name))


@app.route('/folder/<folder>/<chapter>/<note>')
def download_note(folder, chapter, note):
    folder_name = safe_name(folder)
    chapter_name = safe_name(chapter)
    note_name = safe_name(note)
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    return send_from_directory(path, note_name, as_attachment=True)


@app.route('/folder/<folder>/<chapter>/chapter.docx')
def download_chapter_docx(folder, chapter):
    folder_name = safe_name(folder)
    chapter_name = safe_name(chapter)
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    return send_from_directory(
        path,
        'chapter.docx',
        as_attachment=True,
        download_name=f"{chapter_name}.docx",
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
