# Novel Writing App

A small Flask-based web application for organizing folders, chapters and notes. A sidebar file tree provides quick access to all content. Notes and chapters are saved as RTF files and can be downloaded to your local machine. The editor supports basic formatting such as bold, italics and underline.

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
