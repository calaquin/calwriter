import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

app = Flask(__name__)
app.secret_key = 'change-this'

DATA_DIR = os.path.join(os.getcwd(), 'data')

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)


def safe_name(name: str) -> str:
    return ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-')).rstrip()


def rtf_wrap(text: str) -> str:
    escaped = text.replace('\n', '\\par ')
    return '{\\rtf1\\ansi\\deff0 {\\fonttbl {\\f0 Arial;}}\\f0 ' + escaped + '}'


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
    return render_template('folder.html', folder=folder_name, chapters=chapters)


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
    notes = [n for n in os.listdir(path) if n.endswith('.rtf')]
    return render_template('chapter.html', folder=folder_name, chapter=chapter_name, notes=notes)


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
        f.write(rtf_wrap(text))
    return redirect(url_for('view_chapter', folder=folder_name, chapter=chapter_name))


@app.route('/folder/<folder>/<chapter>/<note>')
def download_note(folder, chapter, note):
    folder_name = safe_name(folder)
    chapter_name = safe_name(chapter)
    note_name = safe_name(note)
    path = os.path.join(DATA_DIR, folder_name, chapter_name)
    return send_from_directory(path, note_name, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
