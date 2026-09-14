# Known Issues Backlog

This document tracks persistent known issues, limitations, and deferred technical discoveries in CalWriter.

---

## Active & Tracked Issues

### [ISSUE-001] Session Cookie Discarded Over Non-HTTPS Connections
- **Status:** Open (Documented Behavior)
- **Severity:** Medium
- **Component:** Backend / Auth
- **Description:** Setting `SESSION_COOKIE_SECURE=true` in local development over HTTP (`localhost`) causes modern browsers to reject session cookies upon login, creating a redirect loop back to `/login`.
- **Mitigation:** `.env.example` defaults `SESSION_COOKIE_SECURE=false` for local development. Set to `true` only when deploying behind HTTPS.

### [ISSUE-002] Concurrent Root Book Delete Cascades
- **Status:** Open (Mitigated)
- **Severity:** Low
- **Component:** Database / Teardown
- **Description:** Deleting books with deeply nested recursive chapters requires multi-row chapter batch deletion prior to root folder deletion due to `ON DELETE RESTRICT` constraints on `parent_chapter_id`.
- **Mitigation:** Enforced in `tests/conftest.py` cleanup fixtures and `services.py` cascade handlers.

