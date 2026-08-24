"""Tests for the shared hierarchy validator (services.py): depth math,
cycle detection, XOR-parent enforcement, sibling-name uniqueness, and the
parent-with-children delete restriction. Covers the P0.3 spec's hard
requirements directly against services.* -- no HTTP layer involved.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Chapter
import services


# --- depth math -------------------------------------------------------

def test_chapter_directly_under_folder_is_depth_zero(make_book, make_folder, make_chapter):
    book = make_book()
    ch = make_chapter(folder=book)
    assert services.chapter_depth(ch) == 0


def test_chapter_depth_increments_per_ancestor_chapter(make_book, make_chapter):
    book = make_book()
    a = make_chapter(folder=book)
    b = make_chapter(parent_chapter=a)
    c = make_chapter(parent_chapter=b)
    assert services.chapter_depth(a) == 0
    assert services.chapter_depth(b) == 1
    assert services.chapter_depth(c) == 2


def test_chapter_can_reach_exactly_five_levels_not_four_or_six(make_book, make_chapter):
    """MAX_CHAPTER_DEPTH = 4 (0-indexed) must permit exactly 5 levels
    (depths 0-4) -- the precise off-by-one revision 3 of the plan fixed."""
    book = make_book()
    node = make_chapter(folder=book)
    for _ in range(services.MAX_CHAPTER_DEPTH):
        node = make_chapter(parent_chapter=node)
    assert services.chapter_depth(node) == services.MAX_CHAPTER_DEPTH == 4
    # A 6th level (nesting one more under the depth-4 node) must be rejected.
    with pytest.raises(services.HierarchyError):
        services.validate_chapter_parent(None, new_parent_chapter=node)


def test_folder_can_reach_the_folder_depth_cap(make_book, make_folder):
    book = make_book()
    node = book
    for _ in range(services.MAX_FOLDER_DEPTH):
        node = make_folder(node)
    assert services.folder_depth(node) == services.MAX_FOLDER_DEPTH
    with pytest.raises(services.HierarchyError):
        services.validate_folder_parent(None, node)


# --- subtree-depth-on-move ---------------------------------------------

def test_move_accounts_for_moved_subtrees_deepest_descendant(make_book, make_chapter):
    """A leaf chapter can move to depth MAX_CHAPTER_DEPTH, but a chapter
    that itself has 2 levels of descendants can't -- the move must be
    rejected based on the SUBTREE's resulting depth, not just the moved
    node's own."""
    book = make_book()
    # Build a target chain reaching depth MAX_CHAPTER_DEPTH - 2 (so nesting
    # a leaf under it lands exactly at the cap, but nesting a 2-deep
    # subtree under it would exceed it by 2).
    target = make_chapter(folder=book)
    for _ in range(services.MAX_CHAPTER_DEPTH - 2):
        target = make_chapter(parent_chapter=target)

    leaf = make_chapter(folder=book)
    services.validate_chapter_parent(leaf.id, new_parent_chapter=target)  # must not raise

    subtree_root = make_chapter(folder=book)
    make_chapter(parent_chapter=make_chapter(parent_chapter=subtree_root))
    with pytest.raises(services.HierarchyError):
        services.validate_chapter_parent(subtree_root.id, new_parent_chapter=target)


def test_leaf_chapter_moved_under_depth_zero_chapter_lands_at_depth_one(make_book, make_chapter):
    """Regression test for the revision-2 off-by-one: new_root_depth must
    not double-count the hop already folded into it."""
    book = make_book()
    parent = make_chapter(folder=book)
    leaf = make_chapter(folder=book)
    services.validate_chapter_parent(leaf.id, new_parent_chapter=parent)  # must not raise
    leaf.parent_chapter_id = parent.id
    leaf.folder_id = None
    db.session.commit()
    assert services.chapter_depth(leaf) == 1


# --- cycle / self-parent rejection --------------------------------------

def test_chapter_cannot_be_nested_inside_itself(make_book, make_chapter):
    book = make_book()
    ch = make_chapter(folder=book)
    with pytest.raises(services.HierarchyError):
        services.validate_chapter_parent(ch.id, new_parent_chapter=ch)


def test_chapter_cannot_be_nested_inside_its_own_descendant(make_book, make_chapter):
    book = make_book()
    a = make_chapter(folder=book)
    b = make_chapter(parent_chapter=a)
    c = make_chapter(parent_chapter=b)
    with pytest.raises(services.HierarchyError):
        services.validate_chapter_parent(a.id, new_parent_chapter=c)  # direct-into-grandchild
    with pytest.raises(services.HierarchyError):
        services.validate_chapter_parent(a.id, new_parent_chapter=b)  # direct-into-child


def test_folder_cannot_be_moved_into_itself_or_its_descendant(make_book, make_folder):
    book = make_book()
    a = make_folder(book)
    b = make_folder(a)
    with pytest.raises(services.HierarchyError):
        services.validate_folder_parent(a.id, a)
    with pytest.raises(services.HierarchyError):
        services.validate_folder_parent(a.id, b)


def test_book_root_folder_cannot_be_reparented(make_book, make_folder):
    book = make_book()
    other = make_folder(book)
    with pytest.raises(services.HierarchyError):
        services.validate_folder_parent(book.id, other)


def test_folder_move_rejected_across_books(make_book, make_folder):
    book_a = make_book()
    book_b = make_book()
    sub_a = make_folder(book_a)
    with pytest.raises(services.HierarchyError):
        services.validate_folder_parent(sub_a.id, book_b)


def test_chapter_move_allowed_across_books(make_book, make_chapter):
    """Cross-book chapter moves are existing, preserved behavior -- unlike
    folders, this must NOT raise."""
    book_a = make_book()
    book_b = make_book()
    ch = make_chapter(folder=book_a)
    target = make_chapter(folder=book_b)
    services.validate_chapter_parent(ch.id, new_parent_chapter=target)  # must not raise


# --- XOR parent (DB constraint level) -----------------------------------

def test_chapter_requires_exactly_one_parent_at_db_level(make_book, make_chapter):
    """Bypasses the app-level validator entirely to prove chk_chapters_one_parent
    itself is the backstop, for both illegal states."""
    book = make_book()
    existing = make_chapter(folder=book)

    neither = Chapter(book_id=book.id, name='neither-parent-set')
    db.session.add(neither)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    both = Chapter(book_id=book.id, name='both-parents-set', folder_id=book.id, parent_chapter_id=existing.id)
    db.session.add(both)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# --- sibling-name uniqueness scoped to the actual immediate parent ------

def test_nested_chapter_name_collision_only_against_its_own_siblings(make_book, make_chapter):
    book = make_book()
    parent_a = make_chapter(folder=book)
    parent_b = make_chapter(folder=book)
    make_chapter(parent_chapter=parent_a, name='Same Name')
    # A different parent's child with the same name must be fine.
    make_chapter(parent_chapter=parent_b, name='Same Name')
    # But two siblings under the SAME parent must collide.
    with pytest.raises(IntegrityError):
        make_chapter(parent_chapter=parent_a, name='Same Name')
    db.session.rollback()


# --- parent-with-children delete restriction ----------------------------

def test_deleting_chapter_with_children_is_restricted_at_db_level(make_book, make_chapter):
    book = make_book()
    parent = make_chapter(folder=book)
    make_chapter(parent_chapter=parent)
    db.session.delete(parent)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# --- cycle-safety against corrupt/cyclic stored data --------------------

def test_walker_raises_instead_of_hanging_on_corrupt_cyclic_data(make_book, make_chapter):
    """A row-level CHECK constraint can't detect a multi-row cycle (each
    row still has exactly one parent set), so this state is only
    preventable by the app-level validator -- if it's ever bypassed (a
    bug, a manual DB edit), the walkers must raise instead of looping
    forever. No constraint needs touching to construct this: a's parent
    becomes its own child b, still satisfying chk_chapters_one_parent
    per-row."""
    book = make_book()
    a = make_chapter(folder=book)
    b = make_chapter(parent_chapter=a)
    b_id = b.id  # capture before mutating `a`, to avoid a mid-mutation autoflush
    a.folder_id = None
    a.parent_chapter_id = b_id
    db.session.commit()
    try:
        with pytest.raises(services.HierarchyError):
            services.chapter_depth(a)
        with pytest.raises(services.HierarchyError):
            services.descendant_chapter_ids(a.id)
    finally:
        # Break the cycle so the cleanup fixture's cascade-delete (which
        # only reaches chapters still attached to the folder tree) can find
        # and remove these rows instead of leaving them orphaned -- a's
        # parent_chapter_id -> b, b's -> a is a mutual RESTRICT reference
        # that would otherwise block deletion of both forever.
        book_id = book.id  # capture before mutating `a`, same autoflush hazard as above
        a.parent_chapter_id = None
        a.folder_id = book_id
        db.session.commit()
