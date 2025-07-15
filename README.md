# CalWriter

Version 0.5.6

CalWriter is a simple Flask application for drafting novels. It lets you create books with sub-folders and chapters. Each chapter has a notes area that saves automatically as plain text while the chapter itself is stored as a Word document (`.docx`). Basic formatting, automatic saving and a word counter make writing straightforward. Books and chapters can be reordered by dragging them in the list, and a stats page tracks your daily word totals.

## Running with Docker

Build the image and run it:

```bash
docker build -t calwriter:latest .
docker run -d --name calwriter \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  calwriter:latest
```

Visit `http://localhost:5000` to start writing. All data is stored in the
`data` folder you mounted so it persists across upgrades.

The home page includes a link to a simple help screen if you need a reminder of
the features.

## Running with Docker Compose

Using Docker Compose is even easier. Create a file like this:

```yaml
version: "3"
services:
  calwriter:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
```

Run `docker compose up` and open `http://localhost:5000` in your browser.

## License

CalWriter is released under the [MIT License](LICENSE).
