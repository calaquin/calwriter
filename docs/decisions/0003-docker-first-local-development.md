# ADR 0003: Docker-First Local Development Architecture

## Status
Accepted

## Date
2026-08-22 (Formalized 2026-09-14)

## Context
Running PostgreSQL, Flask, and Vite with consistent networking and automatic database migration execution required standardized orchestration.

## Decision
Use Docker Compose with `docker-compose.override.yml` for local development:
1. `app` container bind-mounts Python backend source and runs Flask debug auto-reloading server.
2. `app` executes `alembic upgrade head` on startup via `docker-entrypoint.sh`.
3. `frontend` container runs Vite dev server on port 5173 with API proxying to `app:5000`.
4. `adminer` container runs lightweight DB browser on port 8080 with automated developer autologin.

## Consequences
- Single command bootstrap (`./cw start` or `./setup.sh`).
- Identical runtime environment across developer workstations.
- Adminer remains strictly confined to local dev override.

