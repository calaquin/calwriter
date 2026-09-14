# ADR 0001: Adoption of Workspace Bootstrap Standard v1.0 (Tier 2 Standard)

## Status
Accepted

## Date
2026-09-14

## Context
As the CalWriter codebase evolved, development tooling, local database lifecycle management, environment setup, and AI coding agent governance required standardization without altering the working application architecture.

## Decision
Adopt **Workspace Bootstrap Standard v1.0 (WBS 1.0)** at **Tier 2 (Standard)**:
1. Formalize topology in `workspace-manifest.yaml`.
2. Provide idempotent `setup.sh` zero-to-development bootstrapping.
3. Provide `./cw` unified CLI with standardized vocabulary (`start`, `stop`, `restart`, `status`, `logs`, `doctor`, `info`, `db:*`, `test`, `lint`, `build`, `clean`, `docs:validate`).
4. Externalize backups and runtime logs to `~/.calwriter/`.
5. Enforce strict local-only execution rules for AI coding agents in `AGENTS.md`.
6. Maintain full documentation tree with automated link validation via `scripts/validate_docs.py`.

## Consequences
- Predictable and consistent developer experience.
- Safer database operations with interactive typed confirmations and cryptographic verification.
- Complete documentation that reflects actual architecture.
- Full preservation of existing Flask + React application logic.

