# API Endpoints

All backend API routes are registered under the `/api` prefix in `api.py`. Responses are JSON-encoded.

---

## Authentication & User Management

- `POST /api/login`: Authenticate with username and password. Sets session cookie.
- `POST /api/logout`: Terminate session and clear cookie.
- `GET /api/user`: Retrieve current authenticated user profile and preferences.
- `PUT /api/user/settings`: Update user preferences (timezone, theme, editor defaults).
- `GET /api/users`: List users (admin only).

---

## Books & Folders

- `GET /api/books`: Retrieve all books owned by or shared with current user.
- `POST /api/books`: Create a new book.
- `GET /api/books/<book_id>`: Retrieve book details, sub-folders, and chapters tree.
- `PUT /api/books/<book_id>`: Update book title, description, color, or Book Type.
- `DELETE /api/books/<book_id>`: Delete book and all child resources (Owner only).
- `POST /api/folders`: Create a sub-folder.
- `PUT /api/folders/<folder_id>`: Update sub-folder title, description, or parent.
- `DELETE /api/folders/<folder_id>`: Delete sub-folder.
- `POST /api/folders/<folder_id>/reorder`: Reorder child folders and chapters.

---

## Chapters & Content

- `GET /api/chapters/<chapter_id>`: Retrieve chapter content, notes, and metadata.
- `POST /api/chapters`: Create a new chapter.
- `PUT /api/chapters/<chapter_id>`: Autosave chapter content, title, notes, or completion flag.
- `DELETE /api/chapters/<chapter_id>`: Delete chapter.
- `GET /api/chapters/<chapter_id>/history`: Retrieve version history revisions.
- `POST /api/chapters/<chapter_id>/history/restore`: Restore a previous revision.

---

## Search & Stats

- `GET /api/search?q=<query>&scope=<scope>`: Search 2.0 with context snippets and match highlights.
- `GET /api/stats/workspace`: Workspace-wide writing stats, heatmaps, and streak data.
- `GET /api/stats/book/<book_id>`: Book velocity, contributor breakdown, and stale chapters.
- `POST /api/activity/heartbeat`: Post active writing telemetry and word increments.

---

## Goals

- `GET /api/goals`: List active and completed goals.
- `POST /api/goals`: Create a new goal.
- `PUT /api/goals/<goal_id>`: Update goal parameters.
- `DELETE /api/goals/<goal_id>`: Delete goal.
- `GET /api/goals/<goal_id>/history`: Retrieve periodic goal achievement history.

---

## Export & Import

- `GET /api/export/<resource_type>/<resource_id>?format=<format>`: Export to docx, rtf, txt, md, or calwdb.
- `POST /api/import`: Import a `.calwdb` archive into the current user's library.

