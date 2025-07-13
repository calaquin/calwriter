# Novel Writing App

A small Flask-based web application for organizing books, chapters and notes. A sidebar file tree provides quick access to all books and chapters. Each chapter has a single notes file displayed in the right sidebar and saved automatically as `[ChapterName]_notes.txt`. Notes are stored as plain text while chapters are saved as Word documents (`.docx`) that match the editor layout. Files can be downloaded and both chapters and books can be deleted. The editor supports basic formatting such as bold, italics, underline, indenting and paragraph breaks. A word counter sits above the notes sidebar and updates as you type.

## Running with Docker

Build the Docker image:

```bash
docker build -t novel-app .
```

Run the container with a volume mounted for persistent storage:

```bash
docker run -p 5000:5000 -v $(pwd)/data:/app/data novel-app
```

The application will be accessible at `http://localhost:5000`.
