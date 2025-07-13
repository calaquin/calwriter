# Novel Writing App

A small Flask-based web application for organizing chapters, notes, and folders. Notes are saved as RTF files and can be downloaded to your local machine. The note editor supports bold, italics and underline formatting using a simple toolbar.

## Running with Docker

Build the Docker image:

```bash
docker build -t novel-app .
```

Run the container:

```bash
docker run -p 5000:5000 novel-app
```

The application will be accessible at `http://localhost:5000`.
