# Export & Import System

CalWriter features a robust multi-format document exporter and a portable book archive format (`.calwdb`).

---

## 1. Document Exporters

CalWriter can compile and export individual chapters, sub-folders, or entire books into four standard document formats:

- **Microsoft Word (`.docx`)**:
  - Built using `python-docx`.
  - Preserves hierarchical heading levels (Book title, Folder headings, Chapter headings).
  - Handles styled lists (bulleted, numbered, multi-level nested, checklists) and inline formatting.
- **Rich Text Format (`.rtf`)**:
  - Cross-platform formatted text output compatible with Scrivener, WordPad, and TextEdit.
- **Markdown (`.md`)**:
  - Clean GitHub Flavored Markdown representation of chapter hierarchies and prose.
- **Plain Text (`.txt`)**:
  - Stripped plain text output formatted with standardized paragraph breaks.

---

## 2. Portable Book Archives (`.calwdb`)

### Purpose & Scope
A `.calwdb` file is a portable JSON-formatted archive that encapsulates a user's book content for transfer between different CalWriter instances or standalone archiving.

### Format Features (v4)
- Preserves full recursive hierarchy: Books, Folders, and nested Chapters.
- Preserves prose content, author notes, chapter descriptions, and completion flags.
- Preserves Book Types (General, Novel, Journal, Documentation) and custom color themes.
- Remaps all UUID-backed internal references atomically upon import to fresh UUIDs to prevent collisions.
- Does **not** include account credentials, sharing permissions, user goals, version history, or writing telemetry (which require full PostgreSQL database backups).

