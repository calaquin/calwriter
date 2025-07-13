# Novel Writing App

A small Flask-based web application for organizing folders, chapters and notes. A sidebar file tree provides quick access to all content. Notes are displayed in a right sidebar on the chapter page. Notes are saved as plain text files and chapters as Word documents (`.docx`) that look the same as in the editor. Files can be downloaded to your local machine and chapters can be deleted from the editor. The editor supports basic formatting such as bold, italics, underline, indenting and paragraph breaks. A word counter sits above the notes sidebar and updates as you type.

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
