# ADR 0002: Preservation of Dual Backup and Recovery Contract

## Status
Accepted

## Date
2026-08-24 (Formalized 2026-09-14)

## Context
CalWriter requires both a way for users to export their portable books and novels between different servers or share them with others, as well as a full disaster-recovery mechanism for administrators.

## Decision
Maintain two distinct recovery contracts:
1. **`.calwdb` Portable Archive**:
   - Contains only book content, nested folders, chapters, formatting, notes, and internal references.
   - Remaps internal references to fresh UUIDs on import.
   - Does not contain user accounts, shares, goals, or telemetry.
2. **PostgreSQL Database Dump Triads (`./cw db:backup`)**:
   - Contains exact byte-for-byte database snapshot with original UUIDs, user accounts, hashes, and telemetry.
   - Managed under WBS 1.0 with `.dump`, `.sha256`, and `.json` metadata companions.

## Consequences
- Clean separation between user portability and administrator disaster recovery.
- Zero data leakage of user account details across book exports.

