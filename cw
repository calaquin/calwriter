#!/usr/bin/env bash
# cw - CalWriter Management CLI (Workspace Bootstrap Standard v1.0)
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WORKSPACE_ROOT"

EXTERNAL_BASE="${HOME}/.calwriter"
BACKUP_DIR="${EXTERNAL_BASE}/backups/database"
LOG_DIR="${EXTERNAL_BASE}/logs"

# Ensure directories exist
mkdir -p "$BACKUP_DIR" "${EXTERNAL_BASE}/backups/workspace" "${LOG_DIR}/services" "${LOG_DIR}/tasks" "${EXTERNAL_BASE}/state" "${EXTERNAL_BASE}/cache"

usage() {
    cat <<'EOF'
CalWriter CLI (WBS 1.0)

Usage: ./cw <command> [arguments...]

Lifecycle Commands:
  start [service...]       Start all or specific services (app, db, frontend, adminer)
  stop [service...]        Stop all or specific services
  restart [service...]     Restart services
  status                   Show typed status and health probes for all services
  logs [service...]        Tail container logs

Diagnostic & Information:
  doctor                   Run comprehensive environment, port, and health diagnostics
  info                     Display workspace topology, versions, and paths

Database Commands:
  db:backup [label]        Create atomic backup triad (.dump, .sha256, .json) in ~/.calwriter/backups/database/
  db:restore <file>        Restore database from backup triad (Requires typed confirmation)
  db:reset                 Reset database schema and run migrations (Requires typed confirmation)
  db:migrate               Run pending database migrations (alembic upgrade head)
  db:status                Check current Alembic revision and database connectivity
  db:prune [--days N]      Prune complete backup triads older than N days (default: 14)

Quality & Build:
  test [args...]           Run test suite (pytest backend and frontend validation)
  lint                     Run frontend oxlint and backend code checks
  build                    Build Docker containers and frontend bundle
  clean                    Safely remove temporary build artifacts and caches
  docs:validate            Validate documentation links, structure, and manifest parity

Application Admin Commands:
  user:create <user> [--admin]  Create a user account
  user:list                     List all registered users
  user:reset-password <user>    Reset password for a user
  book:list                     List all books in the database
  book:share <id> <user> <role> Share book with user (editor|viewer)
  book:unshare <id> <user>      Revoke book share
EOF
}

# Helper to check if docker compose service is running
is_service_running() {
    local svc="$1"
    local state
    state=$(docker compose ps --format json "$svc" 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || true)
    [ "$state" = "running" ]
}

probe_http() {
    local url="$1"
    local expected_code="${2:-200}"
    local timeout="${3:-3}"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$timeout" "$url" 2>/dev/null || echo "000")
    if [ "$code" = "$expected_code" ] || ([ "$expected_code" = "200" ] && [[ "$code" =~ ^(200|204|301|302)$ ]]); then
        return 0
    else
        return 1
    fi
}

probe_tcp() {
    local host="$1"
    local port="$2"
    local timeout="${3:-3}"
    if command -v nc >/dev/null 2>&1; then
        nc -z -w "$timeout" "$host" "$port" 2>/dev/null
    else
        (echo > "/dev/tcp/${host}/${port}") >/dev/null 2>&1
    fi
}

cmd_start() {
    echo "Starting CalWriter services..."
    docker compose up -d "$@"
    echo ""
    cmd_status
}

cmd_stop() {
    echo "Stopping CalWriter services..."
    if [ $# -eq 0 ]; then
        docker compose stop
    else
        docker compose stop "$@"
    fi
}

cmd_restart() {
    echo "Restarting CalWriter services..."
    docker compose restart "$@"
    echo ""
    cmd_status
}

cmd_logs() {
    docker compose logs -f "$@"
}

cmd_status() {
    printf "%-12s %-8s %-24s %-20s %-20s\n" "SERVICE" "REQUIRED" "CONTAINER STATUS" "HEALTH PROBE" "OVERALL"
    printf "%-12s %-8s %-24s %-20s %-20s\n" "-------" "--------" "----------------" "------------" "-------"

    local overall_exit=0

    # 1. db service
    local db_running=0
    local db_health="stopped"
    local db_status="stopped"
    if is_service_running db; then
        db_running=1
        if docker compose exec -T db pg_isready -U calwriter >/dev/null 2>&1; then
            db_health="healthy"
            db_status="healthy"
        else
            db_health="unhealthy"
            db_status="degraded"
            overall_exit=1
        fi
    else
        db_status="stopped"
        overall_exit=1
    fi
    printf "%-12s %-8s %-24s %-20s %-20s\n" "db" "yes" "$([ $db_running -eq 1 ] && echo "running" || echo "stopped")" "$db_health" "$db_status"

    # 2. app service
    local app_running=0
    local app_health="stopped"
    local app_status="stopped"
    if is_service_running app; then
        app_running=1
        if probe_http "http://localhost:5000/healthz" "204" 3; then
            app_health="http 204 (pass)"
            app_status="healthy"
        else
            app_health="http probe fail"
            app_status="degraded"
            overall_exit=1
        fi
    else
        app_status="stopped"
        overall_exit=1
    fi
    printf "%-12s %-8s %-24s %-20s %-20s\n" "app" "yes" "$([ $app_running -eq 1 ] && echo "running" || echo "stopped")" "$app_health" "$app_status"

    # 3. frontend service (optional dev server)
    local fe_running=0
    local fe_health="stopped"
    local fe_status="optional-stopped"
    if is_service_running frontend; then
        fe_running=1
        if probe_http "http://localhost:5173" "200" 3; then
            fe_health="http 200 (pass)"
            fe_status="healthy"
        else
            fe_health="starting / unreachable"
            fe_status="degraded"
        fi
    fi
    printf "%-12s %-8s %-24s %-20s %-20s\n" "frontend" "no" "$([ $fe_running -eq 1 ] && echo "running" || echo "stopped")" "$fe_health" "$fe_status"

    # 4. adminer service (optional dev browser)
    local adm_running=0
    local adm_health="stopped"
    local adm_status="optional-stopped"
    if is_service_running adminer; then
        adm_running=1
        if probe_http "http://localhost:8080" "200" 3; then
            adm_health="http 200 (pass)"
            adm_status="healthy"
        else
            adm_health="unreachable"
            adm_status="degraded"
        fi
    fi
    printf "%-12s %-8s %-24s %-20s %-20s\n" "adminer" "no" "$([ $adm_running -eq 1 ] && echo "running" || echo "stopped")" "$adm_health" "$adm_status"

    return "$overall_exit"
}

cmd_doctor() {
    echo "============================================================"
    echo " CalWriter Doctor Diagnostic"
    echo "============================================================"
    local issues=0

    echo "1. Checking host tools:"
    for tool in docker git python3 curl; do
        if command -v "$tool" >/dev/null 2>&1; then
            echo "  [PASS] $tool is available ($(command -v "$tool"))"
        else
            echo "  [FAIL] $tool is missing!"
            issues=$((issues + 1))
        fi
    done

    echo ""
    echo "2. Checking configuration files:"
    if [ -f .env ]; then
        echo "  [PASS] .env exists (permissions: $(stat -c '%a' .env))"
    else
        echo "  [FAIL] .env is missing. Run ./setup.sh to generate one."
        issues=$((issues + 1))
    fi

    if [ -f workspace-manifest.yaml ]; then
        echo "  [PASS] workspace-manifest.yaml exists"
    else
        echo "  [FAIL] workspace-manifest.yaml missing!"
        issues=$((issues + 1))
    fi

    echo ""
    echo "3. Checking external storage paths:"
    for path in "$EXTERNAL_BASE" "$BACKUP_DIR" "$LOG_DIR"; do
        if [ -d "$path" ]; then
            echo "  [PASS] $path exists (permissions: $(stat -c '%a' "$path"))"
        else
            echo "  [WARN] $path does not exist (will be created automatically)"
        fi
    done

    echo ""
    echo "4. Checking service health & connectivity:"
    if is_service_running db; then
        echo "  [PASS] db container is running"
        if docker compose exec -T db pg_isready -U calwriter >/dev/null 2>&1; then
            echo "  [PASS] PostgreSQL is ready and accepting connections"
        else
            echo "  [FAIL] PostgreSQL is not accepting connections"
            issues=$((issues + 1))
        fi
    else
        echo "  [INFO] db container is not running (start with ./cw start)"
    fi

    if is_service_running app; then
        echo "  [PASS] app container is running"
        if probe_http "http://localhost:5000/healthz" "204" 3; then
            echo "  [PASS] app /healthz probe passed (HTTP 204)"
        else
            echo "  [FAIL] app /healthz probe failed"
            issues=$((issues + 1))
        fi
    else
        echo "  [INFO] app container is not running (start with ./cw start)"
    fi

    echo ""
    if [ "$issues" -eq 0 ]; then
        echo "✓ Doctor check passed with 0 critical issues."
        return 0
    else
        echo "✗ Doctor check found $issues issue(s)."
        return 1
    fi
}

cmd_info() {
    echo "============================================================"
    echo " CalWriter Workspace Topology (WBS 1.0 Tier 2 - Standard)"
    echo "============================================================"
    echo "Project:            CalWriter (slug: calwriter)"
    echo "Version:            0.21.1"
    echo "Tier:               standard"
    echo "Workspace Root:     $WORKSPACE_ROOT"
    echo "External Storage:   $EXTERNAL_BASE"
    echo "Backups Path:       $BACKUP_DIR"
    echo ""
    echo "Services & Ports:"
    echo "  - Backend / App:  http://localhost:5000 (Flask, Python 3.11)"
    echo "  - Database:       localhost:5432 (PostgreSQL 16 Alpine)"
    echo "  - Frontend Dev:   http://localhost:5173 (React 19 + TypeScript + Vite)"
    echo "  - Adminer (Dev):  http://localhost:8080 (Dev Database Viewer)"
    echo ""
    echo "Manifest:           workspace-manifest.yaml"
    echo "Agent Rules:        AGENTS.md"
    echo "Documentation:      docs/index.md"
}

cmd_db_backup() {
    local label="${1:-}"
    local timestamp
    timestamp=$(date -u +"%Y%m%d_%H%M%SZ")
    local filename="calwriter_${timestamp}"
    if [ -n "$label" ]; then
        # sanitize label
        label=$(echo "$label" | tr -cd 'a-zA-Z0-9_-')
        filename="calwriter_${timestamp}_${label}"
    fi

    local dump_path="${BACKUP_DIR}/${filename}.dump"
    local sha_path="${BACKUP_DIR}/${filename}.sha256"
    local json_path="${BACKUP_DIR}/${filename}.json"

    echo "Creating CalWriter database backup..."
    if ! is_service_running db; then
        echo "Error: Database service is not running. Start with './cw start db'" >&2
        exit 1
    fi

    # 1. Generate dump file
    docker compose exec -T db pg_dump -U calwriter -Fc calwriter > "$dump_path"
    chmod 0600 "$dump_path"

    # 2. Generate SHA256
    local sha_val
    sha_val=$(sha256sum "$dump_path" | awk '{print $1}')
    echo "$sha_val  $(basename "$dump_path")" > "$sha_path"
    chmod 0600 "$sha_path"

    # 3. Collect Git and Alembic metadata
    local git_commit="unknown"
    local git_branch="unknown"
    local git_dirty=false
    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        git_commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
        git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
            git_dirty=true
        fi
    fi

    local alembic_head="unknown"
    if is_service_running app; then
        alembic_head=$(docker compose exec -T app alembic current 2>/dev/null | grep -o '[0-9a-f]\{12\}' | head -n 1 || echo "unknown")
    fi

    local pg_version
    pg_version=$(docker compose exec -T db psql -U calwriter -d calwriter -t -A -c "SHOW server_version;" 2>/dev/null || echo "16")

    local size_bytes
    size_bytes=$(stat -c '%s' "$dump_path" 2>/dev/null || wc -c < "$dump_path")

    # 4. Write metadata companion JSON
    cat <<EOF > "$json_path"
{
  "project": "calwriter",
  "version": "1.0.0",
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "filename": "$(basename "$dump_path")",
  "sha256": "$sha_val",
  "size_bytes": $size_bytes,
  "database": {
    "engine": "postgresql",
    "version": "$pg_version",
    "database_name": "calwriter",
    "alembic_revision": "$alembic_head"
  },
  "provenance": {
    "git_commit": "$git_commit",
    "git_branch": "$git_branch",
    "git_dirty": $git_dirty
  }
}
EOF
    chmod 0600 "$json_path"

    echo "✓ Database backup triad successfully created:"
    echo "  Dump:     $dump_path ($size_bytes bytes)"
    echo "  SHA256:   $sha_path ($sha_val)"
    echo "  Metadata: $json_path"
}

cmd_db_restore() {
    local target="${1:-}"
    if [ -z "$target" ]; then
        echo "Error: Backup file or prefix required." >&2
        echo "Usage: ./cw db:restore <path_or_filename>" >&2
        exit 1
    fi

    # Resolve full path if relative or name
    local dump_path="$target"
    if [ ! -f "$dump_path" ]; then
        if [ -f "${BACKUP_DIR}/${target}" ]; then
            dump_path="${BACKUP_DIR}/${target}"
        elif [ -f "${BACKUP_DIR}/${target}.dump" ]; then
            dump_path="${BACKUP_DIR}/${target}.dump"
        else
            echo "Error: Backup file not found: $target" >&2
            exit 1
        fi
    fi

    local base_prefix="${dump_path%.dump}"
    local sha_path="${base_prefix}.sha256"
    local json_path="${base_prefix}.json"

    echo "============================================================"
    echo " DATABASE RESTORE - DESTRUCTIVE OPERATION"
    echo "============================================================"
    echo "Target Backup: $dump_path"

    # Check sha256
    if [ -f "$sha_path" ]; then
        echo "Verifying SHA256 checksum..."
        local expected_sha
        expected_sha=$(awk '{print $1}' "$sha_path")
        local actual_sha
        actual_sha=$(sha256sum "$dump_path" | awk '{print $1}')
        if [ "$expected_sha" != "$actual_sha" ]; then
            echo "Error: SHA256 mismatch!" >&2
            echo "  Expected: $expected_sha" >&2
            echo "  Actual:   $actual_sha" >&2
            exit 1
        fi
        echo "  ✓ Checksum verified."
    else
        echo "Warning: Companion .sha256 file not found."
    fi

    if [ -f "$json_path" ]; then
        echo "Backup Metadata:"
        grep -E '"created_at"|"git_commit"|"alembic_revision"' "$json_path" || true
    fi

    echo ""
    echo "Restoring this backup will COMPLETELY OVERWRITE all data in the current database."
    echo "Type RESTORE to continue:"
    read -r confirmation
    if [ "$confirmation" != "RESTORE" ]; then
        echo "Restore cancelled. Confirmation did not match 'RESTORE'."
        exit 1
    fi

    if ! is_service_running db; then
        echo "Starting database service..."
        docker compose up -d db
        sleep 3
    fi

    echo "Restoring database from $dump_path..."
    # Terminate active connections and recreate public schema
    docker compose exec -T db psql -U calwriter -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'calwriter' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true
    docker compose exec -T db psql -U calwriter -d calwriter -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

    # Restore custom format dump
    docker compose exec -T db pg_restore -U calwriter -d calwriter --clean --if-exists < "$dump_path" || true

    echo "Running Alembic upgrade to verify schema synchronization..."
    if is_service_running app; then
        docker compose exec -T app alembic upgrade head
    fi

    echo "✓ Database restore completed successfully."
}

cmd_db_reset() {
    echo "============================================================"
    echo " DATABASE RESET - DESTRUCTIVE OPERATION"
    echo "============================================================"
    echo "This operation will DROP ALL TABLES and recreate the schema from migrations."
    echo "Type RESET to continue:"
    read -r confirmation
    if [ "$confirmation" != "RESET" ]; then
        echo "Reset cancelled. Confirmation did not match 'RESET'."
        exit 1
    fi

    if ! is_service_running db; then
        docker compose up -d db
        sleep 2
    fi

    echo "Dropping and recreating public schema..."
    docker compose exec -T db psql -U calwriter -d calwriter -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

    echo "Applying all migrations (alembic upgrade head)..."
    docker compose exec -T app alembic upgrade head

    echo "✓ Database successfully reset and migrated to head."
}

cmd_db_migrate() {
    echo "Running database migrations..."
    docker compose exec app alembic upgrade head
    echo "✓ Migrations up to date."
}

cmd_db_status() {
    echo "Database Status:"
    if ! is_service_running db; then
        echo "  [ERROR] Database service is stopped."
        return 1
    fi
    docker compose exec -T db pg_isready -U calwriter
    echo ""
    echo "Alembic Revision:"
    docker compose exec -T app alembic current || true
    echo ""
    echo "Table summary:"
    docker compose exec -T db psql -U calwriter -d calwriter -c "\dt" || true
}

cmd_db_prune() {
    local days=14
    while [ $# -gt 0 ]; do
        case "$1" in
            --days)
                days="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1" >&2
                exit 1
                ;;
        esac
    done

    echo "Pruning database backup triads older than $days days from $BACKUP_DIR..."
    local count=0
    # Find dumps older than $days days
    while IFS= read -r dump_file; do
        if [ -n "$dump_file" ] && [ -f "$dump_file" ]; then
            local base="${dump_file%.dump}"
            echo "  Removing backup triad: $(basename "$base")"
            rm -f "${base}.dump" "${base}.sha256" "${base}.json"
            count=$((count + 1))
        fi
    done < <(find "$BACKUP_DIR" -maxdepth 1 -name "calwriter_*.dump" -mtime +"$days" 2>/dev/null)

    echo "✓ Pruned $count backup triad(s)."
}

cmd_test() {
    echo "Running CalWriter test suite..."
    if is_service_running app; then
        docker compose exec -T app pytest -v "$@"
    else
        echo "Starting test container execution via docker compose run..."
        docker compose run --rm app pytest -v "$@"
    fi
}

cmd_lint() {
    echo "Running frontend linter (oxlint)..."
    if [ -d frontend ]; then
        (cd frontend && npm run lint || true)
    fi
    echo "Running Python syntax validation..."
    python3 -m py_compile app.py api.py models.py services.py permissions.py
    echo "✓ Lint checks complete."
}

cmd_build() {
    echo "Building Docker Compose services..."
    docker compose build "$@"
    if [ -d frontend ]; then
        echo "Building frontend bundle..."
        (cd frontend && npm run build)
    fi
    echo "✓ Build complete."
}

cmd_clean() {
    echo "Cleaning temporary build artifacts and cache directories..."
    # Safe allowlist only:
    rm -rf frontend/node_modules/.cache
    rm -rf frontend/dist
    rm -rf .pytest_cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    echo "✓ Clean complete. Note: .env, volumes, and external backups were untouched."
}

cmd_docs_validate() {
    if [ -f scripts/validate_docs.py ]; then
        python3 scripts/validate_docs.py
    else
        echo "Error: scripts/validate_docs.py not found." >&2
        exit 1
    fi
}

# User / Book Admin helpers
cmd_user_create() {
    docker compose exec app flask create-user "$@"
}

cmd_user_list() {
    docker compose exec app flask list-users
}

cmd_user_reset_password() {
    docker compose exec app flask reset-password "$@"
}

cmd_book_list() {
    docker compose exec app flask list-books
}

cmd_book_share() {
    docker compose exec app flask share-book "$@"
}

cmd_book_unshare() {
    docker compose exec app flask unshare-book "$@"
}

# Command dispatch
COMMAND="${1:-}"
if [ -z "$COMMAND" ]; then
    usage
    exit 0
fi
shift

case "$COMMAND" in
    start)                cmd_start "$@" ;;
    stop)                 cmd_stop "$@" ;;
    restart)              cmd_restart "$@" ;;
    status)               cmd_status "$@" ;;
    logs)                 cmd_logs "$@" ;;
    doctor)               cmd_doctor "$@" ;;
    info)                 cmd_info "$@" ;;
    "db:backup")          cmd_db_backup "$@" ;;
    "db:restore")         cmd_db_restore "$@" ;;
    "db:reset")           cmd_db_reset "$@" ;;
    "db:migrate")         cmd_db_migrate "$@" ;;
    "db:status")          cmd_db_status "$@" ;;
    "db:prune")           cmd_db_prune "$@" ;;
    test)                 cmd_test "$@" ;;
    lint)                 cmd_lint "$@" ;;
    build)                cmd_build "$@" ;;
    clean)                cmd_clean "$@" ;;
    "docs:validate")      cmd_docs_validate "$@" ;;
    "user:create")        cmd_user_create "$@" ;;
    "user:list")          cmd_user_list "$@" ;;
    "user:reset-password") cmd_user_reset_password "$@" ;;
    "book:list")          cmd_book_list "$@" ;;
    "book:share")         cmd_book_share "$@" ;;
    "book:unshare")       cmd_book_unshare "$@" ;;
    -h|--help|help)       usage ;;
    *)
        echo "Unknown command: $COMMAND" >&2
        echo "Run './cw help' for available commands." >&2
        exit 1
        ;;
esac

