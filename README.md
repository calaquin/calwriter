# CalWriter

Version 0.3.9

CalWriter is a small Flask-based web application for organizing books, sub-folders, chapters and notes. A sidebar file tree provides quick access to all content. Each chapter has a single notes file displayed in the right sidebar and saved automatically as `[ChapterName]_notes.txt`. Notes are stored as plain text while chapters are saved as Word documents (`.docx`) that match the editor layout. Files save automatically as you type and can be downloaded. Books can contain nested sub-folders so you can organize chapters however you like and rearrange them in the book settings page. The editor supports basic formatting such as bold, italics and underline with a live word counter above the notes. Each book page includes links to statistics and settings for renaming and adding a short description and specifying the author. Chapters include download and delete buttons. Application settings let you switch to dark mode and choose colors for the sidebar, text and background which persist between sessions. A reset option restores the default colors and the sidebar tree can be collapsed for easier navigation. A sidebar search box lets you find text across all chapters and notes. Book settings let you rename chapters and sub-folders, and you can export all chapters in a folder as one DOCX file. The statistics view now shows a bar graph of daily word counts with a configurable range.

## Running with Docker

Build the Docker image:

```bash
docker build -t calwriter .
```

Run the container with a volume mounted for persistent storage. The application
stores all books and chapters in `/app/data` by default. Bind a host directory
or a named Docker volume to that location so the data survives container
updates:

```bash
docker run -p 5000:5000 -v calwriter_data:/app/data calwriter
```

The application will be accessible at `http://localhost:5000`.

## Running with Docker Compose

You can also run the application with Docker Compose. The provided compose file
creates a named volume `data` so your books and chapters persist between runs.
The `DATA_DIR` environment variable defaults to `/app/data` and is set
explicitly in `docker-compose.yml`.

```bash
docker compose up
```

Point your browser to `http://localhost:5000` once the server is running.
