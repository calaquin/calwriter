import enum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        # P1.1A: stable format IDs only, never an arbitrary user-supplied
        # string -- see services.JOURNAL_DATE_FORMATS/JOURNAL_TIME_FORMATS,
        # the single source of truth this must be kept in sync with.
        CheckConstraint(
            "journal_date_format IN ("
            "'long_month_day_year', 'short_month_day_year', 'day_long_month_year', 'day_short_month_year', "
            "'us_numeric', 'day_first_numeric', 'iso', 'weekday_long')",
            name="chk_users_journal_date_format",
        ),
        CheckConstraint("journal_time_format IN ('12_hour', '24_hour')", name="chk_users_journal_time_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # IANA identifier (e.g. America/New_York), never a fixed UTC offset.
    # Nullable only until the browser records its detected zone after the
    # user's first post-migration login; server-side calendar logic safely
    # falls back to UTC during that brief window.
    timezone: Mapped[str | None] = mapped_column(String(64))
    # P1.1A: user-level defaults for Journal day-Chapter names and Write
    # Today timestamps -- account settings, not Book metadata (see
    # services.format_journal_date/format_journal_time), and deliberately
    # NOT part of .calwdb (a portable *Book* archive). For a shared
    # Journal, the *Book owner's* row is what's read, exactly like
    # timezone above -- an Editor's own preferences never apply to another
    # owner's Journal generation.
    journal_date_format: Mapped[str] = mapped_column(String(32), nullable=False, server_default='long_month_day_year')
    journal_time_format: Mapped[str] = mapped_column(String(16), nullable=False, server_default='12_hour')
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Folder(db.Model):
    """A folder in the book tree. A row with parent_id IS NULL is a "book"."""

    __tablename__ = "folders"
    __table_args__ = (
        CheckConstraint("parent_id IS NOT NULL OR owner_id IS NOT NULL", name="chk_root_owner"),
        UniqueConstraint("parent_id", "name", name="uq_folders_parent_name"),
        CheckConstraint(
            "book_type IS NULL OR book_type IN ('general', 'novel', 'journal', 'documentation')",
            name="chk_folders_book_type",
        ),
        CheckConstraint(
            "journal_month IS NULL OR (journal_month >= 1 AND journal_month <= 12)",
            name="chk_folders_journal_month_range",
        ),
        CheckConstraint(
            "journal_month IS NULL OR journal_year IS NOT NULL",
            name="chk_folders_journal_month_requires_year",
        ),
        # P1.2 Journal automation's own generated year/month Folders, keyed
        # by this metadata rather than name/position -- see journal_year's
        # docstring. Partial (WHERE ...IS NOT NULL): an ordinary Folder's
        # NULL/NULL row never participates in either uniqueness check.
        Index(
            "uq_folders_journal_year", "book_id", "journal_year",
            unique=True, postgresql_where=text("journal_year IS NOT NULL AND journal_month IS NULL"),
        ),
        Index(
            "uq_folders_journal_year_month", "book_id", "journal_year", "journal_month",
            unique=True, postgresql_where=text("journal_year IS NOT NULL AND journal_month IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), index=True
    )
    # Denormalized pointer to the top-level ancestor's id (self, on a root row).
    # Lets every permission/listing query filter on book_id with no special-casing
    # for "am I the root folder" -- see permissions.py.
    # NOT NULL + self-referential: when creating a new book (root row), generate
    # the id client-side (uuid.uuid4()) and INSERT id and book_id together in one
    # statement (Postgres checks FK constraints post-statement, so a row
    # referencing itself in a single INSERT is valid) rather than insert-then-update.
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author: Mapped[str] = mapped_column(Text, nullable=False, default="")
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    # Whether a chapter's editor may show the book's color as a subtle
    # background tint (see Chapter.show_book_color). Applies to this folder
    # and everything nested under it -- turning it off on a sub-folder (or
    # the book root itself) opts that whole branch out, same AND-of-ancestors
    # semantics as chapter_effective_book_color in api.py.
    show_book_color: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # P1.2 Book Types. Set (to one of 'general'/'novel'/'journal'/
    # 'documentation') only on a root/Book row; NULL on an ordinary
    # sub-folder -- application logic (not a NOT NULL constraint, since a
    # single books/folders table serves both) treats a root row's NULL as
    # unmigrated/invalid, never as a valid fifth type. Metadata + optional
    # behavior layered on the existing Folder, deliberately not a separate
    # Journal/Novel/Documentation model -- see services.BOOK_TYPES.
    book_type: Mapped[str | None] = mapped_column(String(32))
    # P1.2 Journal automation's generated year/month Folders. These are
    # identity markers the app uses to relocate its own generated
    # structure, NOT layout enforcement: renaming or moving a Folder that
    # carries this metadata never clears it, and the app must never rename/
    # move a Folder back to "repair" it -- see journal_write_today's
    # docstring. journal_year alone (journal_month NULL) marks a year
    # Folder; both set marks a month Folder; both NULL (the common case) is
    # an ordinary Folder that plays no part in Journal resolution.
    journal_year: Mapped[int | None] = mapped_column(Integer)
    journal_month: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # passive_deletes=True on all three: the DB already has ON DELETE CASCADE
    # on every FK here, so let Postgres cascade the delete directly rather than
    # having SQLAlchemy load related rows and null their FK first (which would
    # violate the NOT NULL constraints on folders.book_id / chapters.folder_id).
    owner = relationship("User", foreign_keys=[owner_id])
    children = relationship(
        "Folder",
        foreign_keys=[parent_id],
        backref=db.backref("parent", remote_side=[id]),
        passive_deletes=True,
    )
    chapters = relationship(
        "Chapter", foreign_keys="Chapter.folder_id", back_populates="folder", passive_deletes=True
    )
    shares = relationship(
        "ResourceShare",
        foreign_keys="ResourceShare.folder_id",
        back_populates="folder",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def is_book(self) -> bool:
        return self.parent_id is None


class Chapter(db.Model):
    """A chapter's immediate parent is exactly one of `folder_id` (a direct
    child of a Folder) or `parent_chapter_id` (nested inside another
    Chapter) -- never both, never neither, enforced by
    chk_chapters_one_parent. `book_id` is always set regardless of which
    kind of parent this chapter has (denormalized pointer to the root book,
    same rationale as Folder.book_id) -- see services.HierarchyError and
    friends for the depth/cycle rules governing how a chapter's parent may
    change, and services.nearest_folder_for_chapter for resolving a nested
    chapter's containing Folder when one is needed (book color, breadcrumb,
    sharing ancestor-walk)."""

    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("folder_id", "name", name="uq_chapters_folder_name"),
        UniqueConstraint("parent_chapter_id", "name", name="uq_chapters_parent_chapter_name"),
        CheckConstraint(
            "(folder_id IS NOT NULL)::int + (parent_chapter_id IS NOT NULL)::int = 1",
            name="chk_chapters_one_parent",
        ),
        Index("ix_chapters_search_tsv", "search_tsv", postgresql_using="gin"),
        Index(
            "uq_chapters_journal_date", "book_id", "journal_date",
            unique=True, postgresql_where=text("journal_date IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), index=True
    )
    # A chapter nested inside another chapter, instead of directly under a
    # Folder -- exactly one of folder_id/parent_chapter_id is ever set (see
    # class docstring). RESTRICT, not CASCADE (unlike Folder.parent_id):
    # there's no trash/restore in this app, so deleting a chapter that still
    # has children is rejected at the API layer with a friendly error
    # before it would ever reach this constraint -- this is the backstop
    # against any path that skips that check, not the primary guard. A
    # chapter reads as a document to users, not a container, so silently
    # cascading a delete through a nested outline would be a much worse
    # surprise than folder delete's existing (and unrelated) cascade.
    parent_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="RESTRICT"), index=True
    )
    # Denormalized, same rationale as Folder.book_id. Set from whichever
    # parent a chapter has; updated for an entire moved subtree when a
    # cross-book move changes it (see services.validate_chapter_parent).
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Manually toggled in Chapter Settings (not inferred from content) -- a
    # timestamp rather than a bare flag so a chapter-count goal can check
    # "completed within this goal's current period", not just "is complete
    # right now". Cleared back to NULL if the user toggles it back off.
    completed_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    # Per-chapter opt-out of the book-color background tint (Chapter Settings).
    # The tint only actually shows when this AND every ancestor folder's AND
    # the book's own show_book_color are all true -- see
    # api.chapter_effective_book_color.
    show_book_color: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Lifetime count of ChapterVersion checkpoints ever written for this
    # chapter, incremented in services.snapshot_chapter_version. Tracked
    # separately from the ChapterVersion rows themselves because those are
    # pruned down to the most recent 50 -- this column is the only accurate
    # "revision count" once a chapter has been snapshotted more than that.
    version_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # P1.2 Journal automation's day Chapters. The authoritative identity of
    # "this is the Journal entry for 2026-08-29" -- independent of name,
    # current Folder, or Book Type; a renamed/moved day Chapter is still
    # found by journal_write_today via this column, never by name. NULL for
    # every ordinary chapter. uq_chapters_journal_date (see __table_args__)
    # is the "one Journal Chapter per calendar day per Book" invariant.
    journal_date: Mapped["Date | None"] = mapped_column(Date)
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(name, '') || ' ' || coalesce(content_html, '') || ' ' || coalesce(notes_text, ''))",
            persisted=True,
        ),
    )

    folder = relationship("Folder", foreign_keys=[folder_id], back_populates="chapters")
    # No passive_deletes=True here (unlike Folder.children): that flag means
    # "trust the DB's ON DELETE CASCADE to handle it," which doesn't apply
    # to parent_chapter_id's RESTRICT FK.
    children = relationship(
        "Chapter", foreign_keys=[parent_chapter_id], backref=db.backref("parent_chapter", remote_side=[id])
    )


class ChapterVersion(db.Model):
    """A content checkpoint for a chapter, so an accidental overwrite or bad
    edit can be recovered. Written server-side (see api.py) at most once per
    ~5 minutes of active editing, not on every autosave -- otherwise this
    would grow one row per keystroke pause. Retention is capped at the most
    recent 50 rows per chapter (pruned alongside insert)."""

    __tablename__ = "chapter_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    chapter = relationship("Chapter", foreign_keys=[chapter_id])


class ChapterPresence(db.Model):
    """Heartbeat row: which users have recently had a chapter open, for a
    lightweight "also editing" indicator. Rows are upserted on heartbeat, not
    inserted per-visit -- one row per (chapter, user) pair, timestamp bumped
    each time. A row older than the "recent" window (see api.py) is treated
    as that user no longer being present, not deleted outright."""

    __tablename__ = "chapter_presence"
    __table_args__ = (UniqueConstraint("chapter_id", "user_id", name="uq_chapter_presence_chapter_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_seen: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Word count reported at the previous heartbeat -- lets the next heartbeat
    # compute how many words were added this interval (see
    # services.record_writing_activity). NULL on a brand-new session (nothing
    # to diff against yet).
    last_word_count: Mapped[int | None] = mapped_column(Integer)
    # Cumulative-since-editor-mount typed/pasted word totals reported at the
    # previous heartbeat -- same idempotent-diff role as last_word_count,
    # just for the input-source-aware counters (see
    # api.api_heartbeat_chapter_presence). Unlike last_word_count these
    # default to 0 rather than NULL: a brand-new session's true cumulative
    # total is 0, not "unknown yet".
    last_typed_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_pasted_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Same idempotent-cumulative-heartbeat baseline role as last_typed_words/
    # last_pasted_words, for the P0.11 deleted-words counter (see
    # ChapterWritingActivity.words_deleted).
    last_deleted_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user = relationship("User")


class ChapterWritingActivity(db.Model):
    """Per-user, per-chapter, per-hour accumulation of active writing time and
    input-source-classified words, fed by the presence heartbeat (see
    api.api_heartbeat_chapter_presence / services.record_writing_activity).
    words_typed is genuine keyboard/composition authoring (goal- and
    WPM-eligible); words_pasted is bulk content brought in via paste or an
    external drop (counted toward total word count, never toward a goal or
    WPM). An interval only counts as "active" (active_seconds) if the client
    reports genuine typing/deleting input happened since the last heartbeat
    -- open-but-idle/reading time, and paste-only intervals, are never
    accumulated, which is what makes WPM/active-time stats exclude downtime
    and immune to paste inflating them. `hour_of_day` (0-23, local to the
    writer) plus `date` lets one table serve both day-granularity stats
    (streak, trend, velocity -- group by date, ignore hour) and the
    day-of-week/time-of-day heatmap (group by date's weekday + hour_of_day,
    ignore the specific date). As of P0.6, `date` and `hour_of_day` are the
    writer's local IANA-timezone calendar bucket at heartbeat time. Earlier
    rows are retained unchanged because no raw event timestamp exists from
    which to reconstruct their historical local bucket honestly.

    words_deleted (P0.11) is genuine keyboard/composition words *removed* --
    a positive cumulative count, not a per-word-provenance ledger (deleting
    a pasted word still counts here; this is activity accounting, not
    tagging every word in the document with an origin). "Words written"
    everywhere in the UI/API is the derived `max(words_typed - words_deleted,
    0)`, never a separate stored column -- see services.words_written_from.
    WPM deliberately keeps using gross words_typed, unaffected by deletions:
    it measures typing activity, not net manuscript growth."""

    __tablename__ = "chapter_writing_activity"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "chapter_id", "date", "hour_of_day",
            name="uq_chapter_writing_activity_user_chapter_date_hour",
        ),
        CheckConstraint("hour_of_day >= 0 AND hour_of_day <= 23", name="chk_chapter_writing_activity_hour_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped["Date"] = mapped_column(Date, nullable=False)
    hour_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    active_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    words_typed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    words_pasted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    words_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user = relationship("User")
    chapter = relationship("Chapter")


class ShareRole(str, enum.Enum):
    editor = "editor"
    viewer = "viewer"


class ResourceShare(db.Model):
    """Grants a user access to either one folder (book root or sub-folder --
    the grant covers that folder and everything nested under it) or one
    chapter. Sharing a whole book is just a share on its root folder row;
    there's no separate book-sharing mechanism."""

    __tablename__ = "resource_shares"
    __table_args__ = (
        CheckConstraint(
            "(folder_id IS NOT NULL)::int + (chapter_id IS NOT NULL)::int = 1",
            name="chk_resource_shares_one_target",
        ),
        UniqueConstraint("folder_id", "user_id", name="uq_resource_shares_folder_user"),
        UniqueConstraint("chapter_id", "user_id", name="uq_resource_shares_chapter_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), index=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[ShareRole] = mapped_column(Enum(ShareRole, name="share_role"), nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    folder = relationship("Folder", foreign_keys=[folder_id], back_populates="shares")
    chapter = relationship("Chapter", foreign_keys=[chapter_id])
    user = relationship("User", foreign_keys=[user_id])


class Invite(db.Model):
    """A one-time signup link an admin generates so a new user can create their
    own account (username + password) themselves, instead of the admin running
    `flask create-user`. Single-use (used_at set on redemption) and expiring --
    admin-only to create (checked in api.py), never open registration."""

    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    used_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    created_by = relationship("User", foreign_keys=[created_by_id])
    used_by = relationship("User", foreign_keys=[used_by_id])


class UserSettings(db.Model):
    """Per-user theme + sidebar-visibility state (was global settings.json /
    open_books.json / closed_folders.json / closed_chapters.json before multi-user)."""

    __tablename__ = "user_settings"

    # Mirrors users.id 1:1 -- always set explicitly to a User's own id by app
    # code (see api.py/app.py), never independently generated.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    dark_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sidebar_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#f0f0f0")
    text_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#000000")
    bg_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#ffffff")
    toolbar_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#dddddd")
    editor_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#ffffff")
    dark_sidebar_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#333333")
    dark_text_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#eeeeee")
    dark_bg_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#222222")
    dark_toolbar_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#555555")
    dark_editor_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#444444")
    # User-wide editor footer preferences. Average WPM is subordinate to the
    # word-count display: the API forces it off when word count is hidden.
    show_word_count: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_average_wpm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    open_book_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    closed_folder_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    closed_chapter_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    # Personal sidebar order for top-level books. Deliberately per-user (unlike
    # Folder.position, which drives shared within-book subfolder/chapter order):
    # different users see different accessible book sets, so one collaborator
    # dragging a book in their sidebar must not reorder another collaborator's view.
    book_order: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    hidden_goal_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    goal_order: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    # At most one goal highlighted with a live progress bar in the sidebar --
    # a single nullable column rather than a boolean flag on Goal, so "only
    # one at a time" holds by construction instead of needing an extra
    # uniqueness check. ondelete=SET NULL: deleting the goal just un-primaries
    # it rather than blocking the delete or leaving a dangling reference.
    primary_goal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"))

    user = relationship("User")


class GoalType(str, enum.Enum):
    words = "words"
    chapters = "chapters"


class GoalCadence(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class Goal(db.Model):
    """A personal writing target, scoped to one folder (book or sub-folder)
    or one chapter. Always private to the user who set it. A `chapters`-type
    goal only ever targets a folder (chapter_id must be NULL); `words`-type
    goals can target either.

    A `words`-type goal's progress is the *gross* words this user personally
    typed into the target during the current period (see
    services.resource_typed_words) -- not net change in the resource's total
    word count. Deleting previously-typed text does not revoke earned
    progress, pasted/programmatically-inserted text never earns any, and a
    collaborator's own typing on a shared resource only ever advances their
    own goal, never another user's. This is a deliberate measure-the-work
    definition, not an accident of the underlying accounting.

    `cadence` doubles as the timeframe-type flag: set -> a recurring goal
    whose period re-anchors every daily/weekly/monthly boundary; NULL -> a
    one-time goal running from start_date to end_date. See
    services.advance_goal_period for how period_start is lazily rolled
    forward on read."""

    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint(
            "(folder_id IS NOT NULL)::int + (chapter_id IS NOT NULL)::int = 1",
            name="chk_goals_one_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    folder_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), index=True)
    # Optional user-chosen label, e.g. "First draft push". Empty string (not
    # NULL, matching Folder/Chapter.description) means none was given, in
    # which case the UI falls back to a generated description like "500
    # words / week".
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    goal_type: Mapped[GoalType] = mapped_column(Enum(GoalType, name="goal_type"), nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    cadence: Mapped[GoalCadence | None] = mapped_column(Enum(GoalCadence, name="goal_cadence"))
    start_date: Mapped["Date"] = mapped_column(Date, nullable=False)
    end_date: Mapped["Date | None"] = mapped_column(Date)
    # Current period's start, re-anchored on each rollover for a recurring
    # goal; fixed at start_date for a one-time goal.
    period_start: Mapped["Date"] = mapped_column(Date, nullable=False)
    # Dead column, kept only for same-release rollback safety (migrations
    # auto-apply on boot over a populated DB -- dropping this immediately
    # would break rolling the app back to a version that still reads it).
    # No code path reads or writes this anymore: word-goal progress is now
    # a live sum over ChapterWritingActivity.words_typed (see
    # services.resource_typed_words), not a captured baseline diff. Slated
    # for removal in a later cleanup migration.
    baseline_word_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
    folder = relationship("Folder", foreign_keys=[folder_id])
    chapter = relationship("Chapter", foreign_keys=[chapter_id])


class GoalPeriodHistory(db.Model):
    """A snapshot of one completed period of a *recurring* goal, recorded
    the moment services.advance_goal_period() rolls past it -- one row per
    elapsed period, even if several rolled by unread between visits, since
    progress is now a date-range sum (services.resource_typed_words) rather
    than a single captured baseline that only the first skipped period
    could ever have used. Goal itself only ever tracks its current period's
    live progress -- this is what lets a past day/week/month be shown after
    the fact. Fixed-range goals never get rows here (they have exactly one
    period, which is just the goal itself). Necessarily starts empty for
    every existing goal and only accumulates going forward -- there's no
    way to reconstruct periods that elapsed before this table existed."""

    __tablename__ = "goal_period_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    goal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped["Date"] = mapped_column(Date, nullable=False)
    period_end: Mapped["Date"] = mapped_column(Date, nullable=False)
    # Snapshot target/goal_type at the time, in case the goal's own target
    # is edited later -- history should reflect what was actually being
    # aimed for in that period, not today's target.
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    current: Mapped[int] = mapped_column(Integer, nullable=False)
    achieved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    goal = relationship("Goal")
