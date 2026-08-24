# CalWriter

<img src="assets/logo.png" alt="CalWriter Logo" width="25%" />

CalWriter is a multi-user novel-writing app: organize books into chapters and
sub-folders, write in a rich-text editor that autosaves, and share a book
with other people as an editor or a read-only viewer.

**Features**

- Organize books with nested sub-folders and chapters
- Chapters and notes save automatically as you type
- Export chapters (or a whole book) to `.docx`
- Drag and drop to reorder books, sub-folders, and chapters
- Share a book with other users as an editor (can edit) or viewer (read-only)
- Search across everything you have access to
- Word-count stats per book
- Customizable colors and dark mode
- Export/import your books as `.calwdb` archives

### Backup and recovery contracts

CalWriter provides two intentionally different recovery mechanisms:

- A `.calwdb` archive is a portable copy of the books visible in the
  exporting user's library. It preserves Books, Folders, nested Chapters,
  ordering, prose, notes, descriptions, completion state, color settings,
  and internal references. Import creates fresh resource UUIDs and remaps
  references to other resources included in the same archive.
- `.calwdb` does not contain accounts, shares, user settings, goals, goal
  history, version history, presence, or writing-activity/stat telemetry.
  Use a PostgreSQL dump/restore when recovering or cloning the complete
  multi-user application state; that path preserves every UUID exactly.

## Running with Docker Compose

CalWriter needs a Postgres database alongside the app itself, so it's run via
Docker Compose rather than a single container image.

```bash
git clone https://github.com/calaquin/calwriter.git
cd calwriter
cp .env.example .env
# edit .env: set SECRET_KEY and POSTGRES_PASSWORD (see the comments in the file
# for how to generate each)
docker compose up -d --build
```

Then create your first login (there's no public signup — accounts are
admin-created):

```bash
docker compose exec app flask create-user <username> --admin
```

Visit `http://localhost:5000` and log in.

### Sharing a book with another user

```bash
docker compose exec app flask create-user <their-username>
docker compose exec app flask list-books                       # find the book's id
docker compose exec app flask share-book <book-id> <their-username> editor
```

Use `viewer` instead of `editor` for read-only access. `flask unshare-book <book-id> <username>` revokes it.

### Other admin commands

`flask list-users`, `flask reset-password <username>`.

## Development

The backend is Flask + SQLAlchemy + Alembic (`app.py`, `api.py`,
`services.py`, `models.py`, `permissions.py`), serving a React + TypeScript
frontend (`frontend/`) built with Vite. For local frontend development with
hot reload, run the backend via Docker Compose as above, then:

```bash
cd frontend
npm install
npm run dev
```

This starts a dev server on `:5173` that proxies `/api` calls to the Flask
backend on `:5000`.

### Browsing the database

`docker compose up -d` also starts an [Adminer](https://www.adminer.org/)
instance at `http://localhost:8080`, pre-authenticated to the `calwriter`
Postgres database -- no login screen. Dev-only (see
`docker-compose.override.yml` and `docker/adminer-index.php`); never enable
this against a real database.

## License

CalWriter is released under the [MIT License](LICENSE).
