# Workspace Bootstrap Guide

This guide details how to initialize and configure a fresh CalWriter development workspace using the WBS 1.0 bootstrap script.

---

## Prerequisites

Ensure the following tools are installed on your local host:
- **Docker** (`>= 24.0.0`)
- **Docker Compose** (`>= 2.20.0`)
- **Python 3.11+**
- **curl** and **git**

---

## One-Step Bootstrap

Run the idempotent setup script from the workspace root:

```bash
./setup.sh
```

### What `setup.sh` Executes:
1. **Prerequisite Verification**: Verifies host binaries (Docker, compose, Python).
2. **External State Setup**: Initializes `~/.calwriter/` (`backups/database/`, `logs/`, `state/`) with secure permissions (`0700` for backups).
3. **Environment Generation**: Generates `.env` from `.env.example` with cryptographically random `SECRET_KEY` and `POSTGRES_PASSWORD` (if not already present). Existing `.env` files are never overwritten.
4. **Tool Permissions**: Ensures `./cw` and `scripts/validate_docs.py` are executable.
5. **Container Build**: Builds the Docker Compose image stack (`calwriter-app`).
6. **Diagnostics**: Executes `./cw doctor` to verify environment readiness.

---

## Initial Admin Account Creation

After booting services, create the primary administrator login:

```bash
# Start the containers
./cw start

# Create the admin user
./cw user:create <username> --admin
```

Visit `http://localhost:5000` (or `http://localhost:5173` for frontend dev server) and log in.

