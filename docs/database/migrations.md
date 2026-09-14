# Database Migrations

CalWriter uses **Alembic** to manage database schema evolution.

---

## Migration Configuration

- Configuration file: `alembic.ini`
- Migration scripts: `alembic/versions/`
- Target metadata: SQLAlchemy `db.metadata` imported from `models.py`

---

## Execution Policies

### 1. Automatic Startup Migration
To prevent schema desynchronization on container deploys, the backend entrypoint (`docker-entrypoint.sh`) executes `alembic upgrade head` before booting the web server.

### 2. Manual Migration via CLI
You can check migration status or apply pending migrations using `./cw`:

```bash
# Check current migration revision vs head
./cw db:status

# Apply all pending migrations
./cw db:migrate
```

### 3. Creating New Migrations
When modifying models in `models.py`, generate a new revision inside the application container:

```bash
docker compose exec app alembic revision --autogenerate -m "Add new field to chapter"
```

Inspect the generated file in `alembic/versions/` before committing.

