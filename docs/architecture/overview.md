# Architecture Overview

CalWriter is a full-stack, multi-user web application designed for authoring books, novels, and structured documentation.

---

## Topology & Components

CalWriter uses a containerized multi-service architecture coordinated by Docker Compose:

```text
               +----------------------------------+
               | Browser (User Interface)         |
               +-----------------+----------------+
                                 |
              HTTP (5173 Dev / 5000 Prod)
                                 |
        +------------------------v------------------------+
        | Frontend (React 19 + TypeScript + Vite)         |
        | - Rich Text Autosaving Editor                   |
        | - Hierarchical Book / Folder / Chapter Tree     |
        | - Search 2.0 & Stats Visualizations             |
        +------------------------+------------------------+
                                 | API Proxy (/api/*)
        +------------------------v------------------------+
        | Backend App (Flask 3.0 + Python 3.11)           |
        | - RESTful API (api.py, services.py)             |
        | - Auth & Permissions (Flask-Login, permissions) |
        | - Export Engines (.docx, .rtf, .txt, .md, .calwdb)|
        +------------------------+------------------------+
                                 | SQLAlchemy 2.0 / Alembic
        +------------------------v------------------------+
        | Database (PostgreSQL 16 Alpine)                 |
        | - Full Relational Schema                        |
        | - Full-Text Substring Search                    |
        | - Advisory Locks for Concurrent Operations      |
        +-------------------------------------------------+
```

---

## Service Inventory

1. **`app` (`http://localhost:5000`)**:
   - Flask backend application serving `/api/*` endpoints and SPA shell in production mode.
   - Runs Gunicorn in production image, Flask debug server in local development.
   - Provides `/healthz` endpoint returning HTTP 204.

2. **`db` (`localhost:5432` / internal network)**:
   - PostgreSQL 16 Alpine container with persistent named volume `db_data`.
   - Uses `pg_isready` for container healthchecks.

3. **`frontend` (`http://localhost:5173`)**:
   - Node 20 container running Vite dev server with Hot Module Replacement (HMR).
   - Proxies `/api` requests to `http://app:5000`.

4. **`adminer` (`http://localhost:8080`)**:
   - Lightweight, dev-only web database administration tool with zero-click autologin.
   - Binds to local loopback; strictly disabled in production.

---

## External Persistence

State that survives container and workspace operations is stored in `~/.calwriter/`:
- `~/.calwriter/backups/database/`: Complete `.dump` + `.sha256` + `.json` triads.
- `~/.calwriter/logs/`: Service and background task logs.
- `~/.calwriter/state/`: Ephemeral state cache.

