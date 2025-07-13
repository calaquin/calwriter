# Novel Writing App

A small Flask-based web application for organizing books, sub-books, chapters and notes. A sidebar file tree provides quick access to all content. Each chapter has a single notes file displayed in the right sidebar and saved automatically as `[ChapterName]_notes.txt`. Notes are stored as plain text while chapters are saved as Word documents (`.docx`) that match the editor layout. Files save automatically as you type and can be downloaded. Books can contain nested sub-books so you can organize chapters however you like. The editor supports basic formatting such as bold, italics and underline with a live word counter above the notes. Each book page includes links to statistics and settings for renaming and adding a short description. Chapters include download and delete buttons. An application settings page lets you switch to dark mode and pick sidebar colors which persist between sessions.

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
