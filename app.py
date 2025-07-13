import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import re

app = Flask(__name__)
app.secret_key = 'change-this'

DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.getcwd(), 'data'))

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)


def safe_name(name: str) -> str:
    return ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-')).rstrip()


def rtf_wrap(text: str) -> str:
    escaped = text.replace('\n', '\\par ')
    return '{\\rtf1\\ansi\\deff0 {\\fonttbl {\\f0 Arial;}}\\f0 ' + escaped + '}'


def html_to_rtf(html: str) -> str:
    """Convert a very small subset of HTML to RTF."""
    text = html.replace('\n', '')
    # simple replacements for bold, italics and underline
    replacements = [
        (r'<strong>', r'\\b '), (r'</strong>', r'\\b0 '),
        (r'<b>', r'\\b '), (r'</b>', r'\\b0 '),
        (r'<em>', r'\\i '), (r'</em>', r'\\i0 '),
        (r'<i>', r'\\i '), (r'</i>', r'\\i0 '),
        (r'<u>', r'\\ul '), (r'</u>', r'\\ul0 '),
        (r'<br>', r'\\line '), (r'<br/>', r'\\line '),
        (r'<div>', ''), (r'</div>', r'\\par '),
        (r'<p>', ''), (r'</p>', r'\\par ')
    ]
    for fr, to in replacements:
        text = text.replace(fr, to)
    text = re.sub(r'<[^>]+>', '', text)  # strip any other tags
    return '{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Arial;}}\\f0 ' + text + '}'


def rtf_to_html(rtf: str) -> str:
    """Convert the limited RTF subset back to HTML for editing."""
    text = rtf
    # strip rtf header and trailing brace
    text = re.sub(r'^\{\\rtf1[^\s]*\\f0 ?', '', text)
    if text.endswith('}'):  # remove closing brace
        text = text[:-1]
    replacements = [
        (r'\\b0', '</strong>'), (r'\\b ', '<strong>'),
        (r'\\i0', '</em>'), (r'\\i ', '<em>'),
        (r'\\ul0', '</u>'), (r'\\ul ', '<u>'),
        (r'\\line', '<br/>'), (r'\\par', '<br/>'),
    ]
    for fr, to in replacements:
        text = text.replace(fr, to)
    return text


def list_chapters(folder: str):
    path = os.path.join(DATA_DIR, folder)
    if os.path.isdir(path):
        return [c for c in os.listdir(path) if os.path.isdir(os.path.join(path, c))]
    return []


def list_notes(folder: str, chapter: str):
    path = os.path.join(DATA_DIR, folder, chapter)
    if os.path.isdir(path):
        return [n for n in os.listdir(path) if n.endswith('.rtf') and n != 'chapter.rtf']
    return []


app.jinja_env.globals['list_chapters'] = list_chapters
app.jinja_env.globals['list_notes'] = list_notes


@app.route('/')
def index():
    folders = [f for f in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, f))]
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
    folders = [f for f in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, f))]
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
    chapter_file = os.path.join(path, 'chapter.rtf')
    chapter_html = ''
    if os.path.isfile(chapter_file):
        with open(chapter_file) as f:
            chapter_html = rtf_to_html(f.read())
    notes = [n for n in os.listdir(path) if n.endswith('.rtf') and n != 'chapter.rtf']
    folders = [f for f in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, f))]
    chapters = [c for c in os.listdir(os.path.join(DATA_DIR, folder_name)) if os.path.isdir(os.path.join(DATA_DIR, folder_name, c))]
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
    note_path = os.path.join(path, f"{title}.rtf")
    with open(note_path, 'w') as f:
        f.write(html_to_rtf(text))
    return redirect(url_for('view_chapter', folder=folder_name, chapter=chapter_name))


@app.route('/folder/<folder>/<chapter>/save', methods=['POST'])
def save_chapter(folder, chapter):
    folder_name = safe_name(folder)
    chapter_name = safe_name(chapter)
    text = request.form.get('text', '')
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    os.makedirs(path, exist_ok=True)
    chapter_file = os.path.join(path, 'chapter.rtf')
    with open(chapter_file, 'w') as f:
        f.write(html_to_rtf(text))
    return redirect(url_for('view_chapter', folder=folder_name, chapter=chapter_name))


@app.route('/folder/<folder>/<chapter>/<note>')
def download_note(folder, chapter, note):
    folder_name = safe_name(folder)
    chapter_name = safe_name(chapter)
    note_name = safe_name(note)
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    return send_from_directory(path, note_name, as_attachment=True)


@app.route('/folder/<folder>/<chapter>/chapter.rtf')
def download_chapter_rtf(folder, chapter):
    folder_name = safe_name(folder)
    chapter_name = safe_name(chapter)
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    return send_from_directory(path, 'chapter.rtf', as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
