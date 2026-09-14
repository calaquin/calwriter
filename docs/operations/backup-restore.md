# Database Backup and Restore Operations

This operational guide details the standard procedure for managing PostgreSQL database backups under WBS 1.0.

---

## 1. Creating a Database Backup

Backups are executed using `./cw db:backup`:

```bash
# Standard backup with UTC timestamp
./cw db:backup

# Backup with descriptive label
./cw db:backup pre-upgrade
```

### Triad Output Files
All backups are saved to `~/.calwriter/backups/database/`:
- `calwriter_<timestamp>_<label>.dump` (Postgres custom archive, mode `0600`)
- `calwriter_<timestamp>_<label>.sha256` (SHA256 checksum)
- `calwriter_<timestamp>_<label>.json` (Metadata companion)

---

## 2. Restoring from a Backup

Restoring a database is a destructive operation that replaces the current database contents.

```bash
./cw db:restore calwriter_20260914_104000Z.dump
```

### Safety Gate:
The CLI will display the backup metadata, verify SHA256 integrity, and require typing `RESTORE`:

```text
Restoring this backup will COMPLETELY OVERWRITE all data in the current database.
Type RESTORE to continue:
```

---

## 3. Pruning Old Backups

Pruning is strictly scoped to `~/.calwriter/backups/database/` and removes only complete triads older than the retention threshold:

```bash
# Prune backups older than 14 days (default)
./cw db:prune

# Prune backups older than 30 days
./cw db:prune --days 30
```

