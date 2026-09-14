# AGENTS.md - Agent Governance and Safety Specification

> **Workspace Bootstrap Standard v1.0 (WBS 1.0) — Tier 2 (Standard)**  
> **Workspace:** CalWriter (`calwriter`)  
> **Effective Date:** 2026-09-14  

---

## 1. Absolute Execution Boundary: Local Machine Only

All AI coding assistants and autonomous agents operating in this workspace are strictly confined to the **local development machine**.

### 1.1 Permitted Autonomous Local Operations
- Editing workspace source files, documentation, and configuration.
- Executing local unit and integration tests, linters, typecheckers, and doc validators.
- Orchestrating local Docker Compose services (`./cw start`, `./cw stop`, `./cw restart`, `./cw status`, `./cw logs`).
- Installing project-scoped dependencies in virtualenvs or node_modules.
- Generating and verifying local database backups (`./cw db:backup`).
- Applying non-destructive local development migrations (`./cw db:migrate`).
- Creating verified, atomic **local Git commits** after all applicable validations pass.
- Reading public documentation, package registries, and remote repositories in a read-only capacity.

### 1.2 Strictly Prohibited Remote Operations
- **No Remote Git Mutations**: `git push`, force-pushing, deleting remote branches, or triggering remote workflows.
- **No Remote Deployments**: Deploying to staging, production, cloud environments, VPS, or remote Docker/Portainer endpoints.
- **No Remote Shell Access**: SSH, SCP, rsync, or remote command execution.
- **No Package or Image Publishing**: Publishing to Docker Hub, GHCR, PyPI, npm, or any artifact registry.
- **No LAN Mutation**: Touching or mutating any other machine or device on the local network.

---

## 2. Sources of Truth Separation

This workspace maintains four strictly separated sources of truth:

| Source of Truth | Authoritative For | Must NOT Become |
|---|---|---|
| `workspace-manifest.yaml` | Machine-readable topology, service definitions, ports, probe endpoints, CLI commands, external paths | A narrative documentation guide |
| `AGENTS.md` | Agent operating boundaries, rules, permissions, Git policies, Definition of Done | A duplicate of architecture manuals |
| `docs/` | Architecture, technical decisions (ADRs), API reference, operations, database schema, security | A runtime topology registry |
| `CHANGELOG.md` | Chronological record of user-facing changes and unreleased developments | A project backlog or architecture doc |

When making changes, update **every affected source of truth**.

---

## 3. Database & Data Safety Guardrails

### 3.1 Database State Is User-Owned Data
- Existing development databases may contain irreplaceable user test data, novels, and writing sessions.
- Agents must **NEVER** automatically restore, reset, truncate, drop, or overwrite an existing database upon test failure or error.
- Destructive operations (`./cw db:reset`, `./cw db:restore`) require interactive typed confirmation (`Type RESET to continue:` / `Type RESTORE to continue:`). Bypassing this prompt is prohibited.

### 3.2 Backup Triads
- Database backups must always create the full triad in `~/.calwriter/backups/database/`:
  1. `.dump` (custom format binary dump)
  2. `.sha256` (checksum file)
  3. `.json` (metadata companion with git commit, branch, dirty status, alembic revision)

---

## 4. Local Git Policy

- **Atomic Commits**: Create focused commits with clear, descriptive messages following conventional format.
- **Validation Before Commit**: Run `./cw lint`, `./cw docs:validate`, and relevant tests prior to creating any commit.
- **History Preservation**: Never amend, rebase, squash, or reset commits that were not created in the current agent session without explicit operator instruction.
- **Dirty Tree Preservation**: Never overwrite or discard unrelated uncommitted modifications in the working tree.

---

## 5. Host & System Configuration Safety

- Never execute `sudo` or modify host-level system packages (`apt`, `dnf`, `pacman`, Homebrew).
- Never modify `/etc`, system firewall rules, or host network interfaces.
- Never overwrite existing `.env` files automatically.

---

## 6. Definition of Done & Completion Report

Every task completed by an agent must conclude with a deterministic completion report classifying all checks and providing the following structured sections:

1. **What Changed & Files Affected**: Summary of modifications.
2. **Schema / API / Config Changes & Migrations**: Any database, API, or configuration changes.
3. **Tests & Verification Results**: Output of test suites and validation runs.
4. **Security / Privacy & Compatibility**: Security impact assessment.
5. **Manual / Deployment Steps Remaining**: Any remaining operator actions (e.g. creating first user).
6. **Known Limitations & Deferred Discoveries**: Any deferred items added to `docs/known-issues.md`.
7. **Working Tree Scope Audit**: Verification that no unintended files were modified.
8. **Documentation & Changelog Updates**: Links to updated docs and changelog entries.
9. **Next Steps**: Recommended follow-ups.

