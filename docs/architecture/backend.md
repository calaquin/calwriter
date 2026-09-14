# Backend Architecture

The backend of CalWriter is built with Python 3.11 using Flask, SQLAlchemy 2.0, Flask-Login, and Alembic.

---

## Core Modules

- **`app.py`**:
  - Application factory and Flask configuration.
  - Secret key loading and session cookie configuration (`SESSION_COOKIE_SECURE`).
  - Route handlers for `/healthz` (HTTP 204 health check) and single-page app static routing (`serve_frontend`).
  - Global `require_login` before-request hook for `/api/*` endpoints.
  - CLI commands registration (`flask create-user`, `flask list-books`, `flask share-book`, etc.).

- **`api.py`**:
  - Flask Blueprint containing RESTful API route definitions:
    - User management & authentication (`/api/login`, `/api/logout`, `/api/user`).
    - Library & Books (`/api/books`, `/api/books/<id>`).
    - Folders & Hierarchy (`/api/folders`, `/api/folders/<id>/reorder`).
    - Chapters & Content (`/api/chapters`, `/api/chapters/<id>`, autosave, version history).
    - Search 2.0 (`/api/search`).
    - Goals & Streaks (`/api/goals`, `/api/goals/<id>/history`).
    - Writing Activity & Stats (`/api/stats`, `/api/activity/heartbeat`).
    - Export & Import (`/api/export/<id>`, `/api/import`).

- **`models.py`**:
  - Declarative SQLAlchemy models:
    - `User`: Accounts, hashed passwords (scrypt/werkzeug), timezone settings.
    - `Folder`: Books (root folders) and nested sub-folders with colors and ordering.
    - `Chapter`: Document nodes supporting nested chapter hierarchies, prose, notes, completion flags.
    - `WritingActivity`: Granular typing vs pasting telemetry, word counts, active time tracking.
    - `Goal` & `GoalHistory`: Word count and chapter completion targets with recurring cadence.
    - `BookShare`: Explicit sharing permissions (`editor`, `viewer`).
    - `InternalReference`: Cross-resource links remapped across imports.

- **`services.py`**:
  - Core business logic domain services:
    - Hierarchy traversal and cycle detection.
    - Word count calculation and WPM threshold logic.
    - Search indexing and snippet extraction with match highlighting.
    - Document exporters (`docx`, `rtf`, `txt`, `md`) and `.calwdb` serializer/deserializer.

- **`permissions.py`**:
  - Role-based access control (RBAC) decorators:
    - `require_book_owner`, `require_book_editor`, `require_book_viewer`.
    - Safe permission inheritance down the folder and chapter hierarchy.

---

## Database Access & Locking

- PostgreSQL transactions are managed via scoped sessions from `Flask-SQLAlchemy`.
- Critical hierarchy re-orderings and import operations employ PostgreSQL row-level advisory locks to prevent concurrent race conditions.

