# CalWriter Documentation

Welcome to the technical documentation for **CalWriter**, a multi-user novel and book writing application.

CalWriter workspace conforms to **Workspace Bootstrap Standard v1.0 (WBS 1.0) Tier 2 (Standard)**.

---

## Documentation Directory Map

### Architecture
- [Architecture Overview](architecture/overview.md) — System architecture, container topology, and component interactions.
- [Backend Architecture](architecture/backend.md) — Flask application, SQLAlchemy ORM, services, and permissions model.
- [Frontend Architecture](architecture/frontend.md) — React 19, TypeScript, React Query, and editor state management.
- [Export & Import System](architecture/export-import.md) — Multi-format exports (.docx, .rtf, .txt, .md) and portable `.calwdb` archives.

### Database
- [Database Schema](database/schema.md) — Core tables: Users, Folders, Chapters, Goals, WritingActivity, BookShares.
- [Migrations](database/migrations.md) — Alembic migration workflow and automatic startup upgrades.
- [Backup & Recovery Contract](database/backup-recovery.md) — Portable `.calwdb` vs full PostgreSQL database backups.

### API Reference
- [API Endpoints](api/endpoints.md) — RESTful JSON endpoints for books, chapters, search, stats, and goals.
- [Authentication & Permissions](api/authentication.md) — Session cookie authentication and role-based access control (Owner, Editor, Viewer).

### Operations
- [Workspace Bootstrap](operations/bootstrap.md) — Zero-to-development setup using `setup.sh`.
- [CLI Reference](operations/cli-reference.md) — Complete command reference for `./cw`.
- [Backup & Restore Guide](operations/backup-restore.md) — Creating, verifying, restoring, and pruning backup triads.
- [Troubleshooting](operations/troubleshooting.md) — Common runtime issues and diagnostic procedures.

### Security
- [Security Model](security/security-model.md) — Authentication, password hashing, session cookies, and network isolation.

### Architectural Decision Records (ADRs)
- [ADR-0001: Adoption of Workspace Bootstrap Standard v1.0](decisions/0001-workspace-bootstrap-standard-adoption.md)
- [ADR-0002: Dual Backup & Recovery Contract](decisions/0002-dual-backup-recovery-contract.md)
- [ADR-0003: Docker-First Local Development Architecture](decisions/0003-docker-first-local-development.md)

### Standards & Quality
- [Known Issues Log](known-issues.md) — Persistent known issues backlog.
- [Test Coverage & Inventory](coverage.md) — Backend and frontend test coverage details.
- [ADR Template](templates/adr-template.md) — Template for authoring new Architecture Decision Records.
- [Issue Template](templates/issue-template.md) — Standard issue documentation template.

