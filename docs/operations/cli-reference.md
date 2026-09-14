# Project CLI Reference (`./cw`)

The `./cw` script is the primary command-line interface for the CalWriter workspace.

---

## Command Reference

### Lifecycle Management

```bash
# Start all services (app, db, frontend, adminer) in the background
./cw start

# Stop all running services
./cw stop

# Restart services
./cw restart

# Display typed status and health probes for all services
./cw status

# Tail logs from all or specific services
./cw logs [service_name]
```

### Diagnostics & Topology

```bash
# Comprehensive health and readiness check
./cw doctor

# Print workspace topology, active ports, and external storage paths
./cw info
```

### Database Operations & Safety

```bash
# Create an atomic backup triad (.dump, .sha256, .json)
./cw db:backup [optional_label]

# Restore database from a backup triad (requires typed interactive confirmation)
./cw db:restore <path_or_filename>

# Reset database schema and rerun all migrations (requires typed confirmation)
./cw db:reset

# Apply pending Alembic migrations
./cw db:migrate

# Inspect current database status and Alembic revision
./cw db:status

# Prune completed backup triads older than N days (default: 14)
./cw db:prune [--days 14]
```

### Quality, Linting & Build

```bash
# Run backend pytest test suite
./cw test [pytest_args...]

# Run frontend oxlint and Python syntax validation
./cw lint

# Build Docker images and frontend production bundle
./cw build

# Clean temporary build caches without touching .env or volumes
./cw clean

# Validate documentation links, structure, and manifest consistency
./cw docs:validate
```

### Application Administration

```bash
# Create a new user account
./cw user:create <username> [--admin]

# List all existing user accounts
./cw user:list

# Reset a user's password
./cw user:reset-password <username>

# List all books in the database
./cw book:list

# Share a book with another user
./cw book:share <book_id> <username> <editor|viewer>

# Revoke book sharing
./cw book:unshare <book_id> <username>
```

