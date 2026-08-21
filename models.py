import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("folders.id", ondelete="CASCADE"), index=True
    )
    # Denormalized pointer to the top-level ancestor's id (self, on a root row).
    # Lets every permission/listing query filter on book_id with no special-casing
    # for "am I the root folder" -- see permissions.py.
    # NOT NULL + self-referential: when creating a new book (root row), pre-fetch
    # the id via nextval('folders_id_seq') and INSERT id and book_id together in
    # one statement (Postgres checks FK constraints post-statement, so a row
    # referencing itself in a single INSERT is valid) rather than insert-then-update.
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author: Mapped[str] = mapped_column(Text, nullable=False, default="")
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="")
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
    collaborators = relationship(
        "BookCollaborator", back_populates="book", cascade="all, delete-orphan", passive_deletes=True
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    folder_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalized, same rationale as Folder.book_id.
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_seen: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User")


class BookRole(str, enum.Enum):
    editor = "editor"
    viewer = "viewer"


class BookCollaborator(db.Model):
    __tablename__ = "book_collaborators"
    __table_args__ = (UniqueConstraint("book_id", "user_id", name="uq_book_collaborators_book_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    book_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[BookRole] = mapped_column(Enum(BookRole, name="book_role"), nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    book = relationship("Folder", foreign_keys=[book_id], back_populates="collaborators")
    user = relationship("User", foreign_keys=[user_id])


class Invite(db.Model):
    """A one-time signup link an admin generates so a new user can create their
    own account (username + password) themselves, instead of the admin running
    `flask create-user`. Single-use (used_at set on redemption) and expiring --
    admin-only to create (checked in api.py), never open registration."""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_by_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    used_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    created_by = relationship("User", foreign_keys=[created_by_id])
    used_by = relationship("User", foreign_keys=[used_by_id])


class UserSettings(db.Model):
    """Per-user theme + sidebar-visibility state (was global settings.json /
    open_books.json / closed_folders.json / closed_chapters.json before multi-user)."""

    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
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
    open_book_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=False, default=list)
    closed_folder_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=False, default=list)
    closed_chapter_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=False, default=list)
    # Personal sidebar order for top-level books. Deliberately per-user (unlike
    # Folder.position, which drives shared within-book subfolder/chapter order):
    # different users see different accessible book sets, so one collaborator
    # dragging a book in their sidebar must not reorder another collaborator's view.
    book_order: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=False, default=list)

    user = relationship("User")
