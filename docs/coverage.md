# Test Coverage and Inventory

CalWriter maintains an automated integration and regression test suite covering backend API endpoints, database operations, and export mechanisms.

---

## Test Inventory (`tests/`)

| Test File | Focus Area | Status |
|---|---|---|
| `test_book_types_and_journal.py` | Book types (Novel, Journal, Doc), journal date formats, write-today idempotency | Verified |
| `test_calwdb_recovery.py` | `.calwdb` v4 archive export, import, reference remapping, rollback safety | Verified |
| `test_chapter_presence_race.py` | Concurrency and chapter presence lock safety | Verified |
| `test_contribution_stats.py` | Multi-user shared book contribution tracking | Verified |
| `test_deletion_and_wpm_threshold.py` | Typed vs deleted words telemetry and WPM threshold calculation | Verified |
| `test_hierarchy.py` | Recursive chapter nesting, move operations, cycle prevention | Verified |
| `test_internal_references.py` | UUID-backed internal cross-links and resolution across moves | Verified |
| `test_journal_formatting.py` | Journal date and 12h/24h timestamp formatting | Verified |
| `test_recursive_stats.py` | Word count aggregation across recursive chapter hierarchies | Verified |
| `test_search_v2.py` | Substring search 2.0, scope filtering, snippet highlighting | Verified |
| `test_stats_terminology.py` | Total words, words written, words pasted consistency | Verified |
| `test_user_timezone.py` | IANA timezone resolution for streaks and writing days | Verified |

---

## Running Verification

Execute the test suite via the workspace CLI:

```bash
# Run full backend test suite
./cw test

# Run specific test module
./cw test tests/test_hierarchy.py

# Run frontend linting & static checks
./cw lint
```

