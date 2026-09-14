#!/usr/bin/env bash
# setup.sh - Zero-to-Development Bootstrap for CalWriter (WBS 1.0)
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WORKSPACE_ROOT"

echo "============================================================"
echo " CalWriter Workspace Bootstrap (WBS 1.0)"
echo "============================================================"

# 1. Verify Prerequisites
echo "[1/6] Checking prerequisites..."
MISSING_PREREQS=0

if ! command -v docker >/dev/null 2>&1; then
    echo "  [ERROR] docker is required but not installed." >&2
    MISSING_PREREQS=1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "  [ERROR] docker compose (v2) is required but not installed." >&2
    MISSING_PREREQS=1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "  [ERROR] python3 is required for local tools." >&2
    MISSING_PREREQS=1
fi

if [ "$MISSING_PREREQS" -ne 0 ]; then
    echo "Please install missing prerequisites and rerun setup.sh." >&2
    exit 1
fi
echo "  ✓ Prerequisites satisfied."

# 2. Initialize External State & Backup Directories
echo "[2/6] Initializing external state directories (~/.calwriter)..."
EXTERNAL_BASE="$HOME/.calwriter"
mkdir -p "$EXTERNAL_BASE/backups/database"
mkdir -p "$EXTERNAL_BASE/backups/workspace"
mkdir -p "$EXTERNAL_BASE/logs/services"
mkdir -p "$EXTERNAL_BASE/logs/tasks"
mkdir -p "$EXTERNAL_BASE/state"
mkdir -p "$EXTERNAL_BASE/cache"

chmod 0700 "$EXTERNAL_BASE/backups" "$EXTERNAL_BASE/backups/database" "$EXTERNAL_BASE/backups/workspace"
echo "  ✓ External directories initialized with secure permissions (0700)."

# 3. Environment & Secrets Setup (Idempotent)
echo "[3/6] Verifying environment configuration..."
if [ ! -f .env ]; then
    if [ ! -f .env.example ]; then
        echo "  [ERROR] .env.example not found." >&2
        exit 1
    fi
    echo "  Creating .env from .env.example..."
    cp .env.example .env

    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" .env
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" .env
    chmod 0600 .env
    echo "  ✓ Generated new .env with cryptographically secure tokens."
else
    echo "  ✓ Existing .env preserved (never overwritten)."
fi

# 4. Make CLI executable
echo "[4/6] Setting permissions on project tools..."
if [ -f ./cw ]; then
    chmod +x ./cw
fi
if [ -f ./scripts/validate_docs.py ]; then
    chmod +x ./scripts/validate_docs.py
fi
echo "  ✓ Tool permissions configured."

# 5. Build Container Images
echo "[5/6] Building Docker Compose services..."
docker compose build

# 6. Run Doctor Diagnostic
echo "[6/6] Running workspace diagnostics..."
if [ -x ./cw ]; then
    ./cw doctor || true
fi

echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " Start services:   ./cw start"
echo " Check status:     ./cw status"
echo " Create admin:     ./cw user:create <username> --admin"
echo " Run test suite:   ./cw test"
echo " Read docs:        docs/index.md"
echo "============================================================"

