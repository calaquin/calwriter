# Database Schema

CalWriter's database schema is modeled in SQLAlchemy and hosted on PostgreSQL 16.

---

## Entity Relationship Summary

```text
+---------------+       +------------------+       +-------------------+
|     User      |       |      Folder      |       |      Chapter      |
|---------------|       |------------------|       |-------------------|
| id (UUID)     |<-----\| id (UUID)        |<-----\| id (UUID)         |
| username      |       | owner_id (FK)    |       | book_id (FK)      |
| password_hash |       | parent_id (FK)   |       | folder_id (FK)    |
| timezone      |       | title            |       | parent_chapter_id |
| is_admin      |       | book_type        |       | title, content    |
+-------+-------+       | color            |       | notes, order_idx  |
        |               +--------+---------+       | is_completed      |
        |                        |                 +---------+---------+
        |                        |                           |
        |               +--------v---------+                 |
        +-------------->|    BookShare     |                 |
        |               |------------------|                 |
        |               | book_id (FK)     |                 |
        |               | user_id (FK)     |                 |
        |               | role (edit/view) |                 |
        |               +------------------+                 |
        |                                                    |
        |       +-------------------+       +----------------v---+
        +------>|       Goal        |       |  WritingActivity   |
        |       |-------------------|       |--------------------|
        |       | user_id (FK)      |       | user_id (FK)       |
        |       | target_type       |       | chapter_id (FK)    |
        |       | target_words      |       | words_typed        |
        |       | cadence           |       | words_deleted      |
        |       +---------+---------+       | active_seconds     |
        |                 |                 +--------------------+
        |       +---------v---------+
        +------>|    GoalHistory    |
                |-------------------|
                | goal_id (FK)      |
                | period_start/end  |
                | achieved (bool)   |
                +-------------------+
```

---

## Key Constraints & Invariants

1. **Hierarchy Integrity**:
   - `Folder` nodes represent either top-level Books (`parent_id = NULL`) or Sub-Folders (`parent_id != NULL`).
   - `Chapter` nodes can be attached to a Folder or nested directly under another parent Chapter (`parent_chapter_id`).
   - Cascading deletions are structured to prevent orphaned descendant nodes while enforcing strict foreign key constraints.

2. **Full-Text & Search Indexing**:
   - Substring searching is optimized across title, content, and notes fields.
   - Text parsing ignores HTML markup to index only author-written text.

3. **Writing Activity Tracking**:
   - Activity rows record differential typed vs pasted words per session, ensuring WPM calculations represent genuine author composition velocity.

