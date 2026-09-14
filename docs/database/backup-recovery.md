# Backup and Recovery Contract

CalWriter provides two distinct, intentionally separated recovery mechanisms:

---

## 1. Portable Book Archives (`.calwdb`)

- **Scope**: User-level library content export and import.
- **Includes**:
  - Book metadata, colors, and Book Types (General, Novel, Journal, Documentation).
  - Nested sub-folders and recursive chapters.
  - Prose content, chapter notes, descriptions, and completion flags.
  - Internal reference relationships (automatically remapped to new UUIDs upon import).
- **Excludes**:
  - User accounts and password hashes.
  - Sharing permissions and collaborator access lists.
  - User goals, goal history, and writing streaks.
  - Writing activity telemetry, active time, and typing vs pasting velocity.
  - Chapter version history and presence logs.
- **Use Case**: Exporting your own book to send to a friend, moving a novel to another CalWriter server, or standalone personal content backups.

---

## 2. Complete PostgreSQL Database Dumps

- **Scope**: Full multi-user system state clone and disaster recovery.
- **Includes**:
  - All database tables, exact UUIDs, user accounts, and credentials.
  - All shared book access rights and permissions.
  - All writing activity telemetry, heatmaps, and WPM statistics.
  - All user goals, history records, and version history.
- **WBS 1.0 Triad Standard**:
  Backups created via `./cw db:backup` produce atomic triads in `~/.calwriter/backups/database/`:
  1. `calwriter_<timestamp>.dump` — PostgreSQL custom binary archive (`pg_dump -Fc`).
  2. `calwriter_<timestamp>.sha256` — SHA256 checksum for corruption verification.
  3. `calwriter_<timestamp>.json` — Structured metadata companion (git hash, branch, dirty status, alembic head revision, engine version).
- **Use Case**: Server migrations, disaster recovery, pre-upgrade snapshots, and full multi-user application state recovery.

