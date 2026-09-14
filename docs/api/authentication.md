# Authentication & Permissions

CalWriter uses session-based cookie authentication backed by `Flask-Login` and a role-based access control (RBAC) hierarchy.

---

## Authentication Flow

1. **Login**:
   - The user posts credentials to `POST /api/login`.
   - Passwords are validated using Werkzeug's secure scrypt/pbkdf2 hash verification.
   - Upon success, Flask-Login sets an `HttpOnly`, `SameSite=Lax` session cookie.

2. **Session Security & TLS**:
   - The `SESSION_COOKIE_SECURE` environment variable controls whether the `Secure` attribute is attached to the cookie.
   - In production (with HTTPS/TLS termination), `SESSION_COOKIE_SECURE=true`.
   - In local development over plain HTTP (`localhost`), `SESSION_COOKIE_SECURE=false` ensures cookies are not discarded by browsers.

3. **Public Endpoints**:
   - All `/api/*` endpoints require an active authenticated session, except:
     - `POST /api/login`
     - `GET /api/version`
     - `GET /api/invite/<token>`
     - `POST /api/invite/<token>/accept`

---

## Permissions Hierarchy

Access to books, sub-folders, and chapters follows an explicit permission model:

| Role | Permissions |
|---|---|
| **Owner** | Full control: create, edit, reorder, delete, manage book settings, share with other users, and export. |
| **Editor** | Read and write: edit chapter prose and notes, create sub-folders/chapters, reorder, view stats, and export. Cannot delete the book or manage shares. |
| **Viewer** | Read-only: browse hierarchy, read chapters, view stats, and export. Cannot modify content or structure. |

Permissions cascade down the entire folder and chapter tree.

