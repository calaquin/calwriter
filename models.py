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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Folder(db.Model):
    """A folder in the book tree. A row with parent_id IS NULL is a "book"."""

    __tablename__ = "folders"
    __table_args__ = (
        CheckConstraint("parent_id IS NOT NULL OR owner_id IS NOT NULL", name="chk_root_owner"),
        UniqueConstraint("parent_id", "name", name="uq_folders_parent_name"),
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
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("folder_id", "name", name="uq_chapters_folder_name"),
        Index("ix_chapters_search_tsv", "search_tsv", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalized, same rationale as Folder.book_id.
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
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(name, '') || ' ' || coalesce(content_html, '') || ' ' || coalesce(notes_text, ''))",
            persisted=True,
        ),
    )

    folder = relationship("Folder", foreign_keys=[folder_id], back_populates="chapters")


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

    user = relationship("User")


class ChapterWritingActivity(db.Model):
    """Per-user, per-chapter, per-hour accumulation of active writing time and
    words written, fed by the presence heartbeat (see
    api.api_heartbeat_chapter_presence / services.record_writing_activity).
    An interval only counts as "active" if the client reports an edit
    actually happened since the last heartbeat -- open-but-idle/reading time
    is never accumulated, which is what makes WPM/active-time stats exclude
    downtime. `hour_of_day` (0-23, local to the server) plus `date` lets one
    table serve both day-granularity stats (streak, trend, velocity -- group
    by date, ignore hour) and the day-of-week/time-of-day heatmap (group by
    date's weekday + hour_of_day, ignore the specific date)."""

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
    words_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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
    or one chapter. Always private to the user who set it -- even on a
    shared resource, each collaborator tracks their own goal against that
    resource's overall word/chapter count (there's no per-author
    attribution in this app). A `chapters`-type goal only ever targets a
    folder (chapter_id must be NULL); `words`-type goals can target either.

    `cadence` doubles as the timeframe-type flag: set -> a recurring goal
    whose period re-anchors every daily/weekly/monthly boundary; NULL -> a
    one-time goal running from start_date to end_date. See
    services.advance_goal_period for how period_start/baseline_word_count
    are lazily rolled forward and (re)captured on read."""

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
    # Word count of the resource at period_start, captured lazily the first
    # time the goal is read on/after that date -- NULL until then. Only used
    # for goal_type == 'words'; progress is current_total - baseline.
    baseline_word_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
    folder = relationship("Folder", foreign_keys=[folder_id])
    chapter = relationship("Chapter", foreign_keys=[chapter_id])


class GoalPeriodHistory(db.Model):
    """A snapshot of one completed period of a *recurring* goal, recorded
    the moment services.advance_goal_period() rolls past it. Goal itself
    only ever tracks its current period's progress (see its baseline_word_count
    comment) -- this is what lets a past day/week/month be shown after the
    fact. Fixed-range goals never get rows here (they have exactly one
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
