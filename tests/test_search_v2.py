"""P1.1: Search 2.0 -- occurrence-level literal search, scoping, pagination.
See services.search_chapter_matches / find_literal_occurrences /
html_to_search_text and api.api_search."""
import uuid

from flask import g

from extensions import db
from models import ResourceShare, ShareRole, User


def login(client, user):
    with client.session_transaction() as session:
        session.clear()
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    g.pop('_login_user', None)


def search(client, **params):
    return client.get('/api/search', query_string=params)


def make_collaborator(cleanup, name='collab'):
    collaborator = User(username=f'{name}-{uuid.uuid4().hex[:12]}', password_hash='x', is_admin=False)
    db.session.add(collaborator)
    db.session.commit()
    cleanup['users'].append(collaborator.id)
    return collaborator


# ---------------------------------------------------------- occurrences --

def test_single_content_occurrence_is_one_result(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book(), name='Chapter A')
    chapter.content_html = '<p>The Talaktei arrived at dusk.</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    resp = search(client, q='Talaktei')
    assert resp.status_code == 200
    data = resp.json
    content_matches = [m for m in data['matches'] if m['source'] == 'content']
    assert len(content_matches) == 1
    assert content_matches[0]['occurrenceIndex'] == 0
    assert content_matches[0]['chapterId'] == str(chapter.id)


def test_multiple_content_occurrences_are_multiple_results_with_correct_indexes(
    app, user, make_book, make_chapter,
):
    chapter = make_chapter(folder=make_book(), name='Chapter B')
    chapter.content_html = '<p>Talaktei one. Talaktei two. Talaktei three.</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    data = search(client, q='Talaktei').json
    content_matches = sorted(
        (m for m in data['matches'] if m['source'] == 'content'), key=lambda m: m['occurrenceIndex']
    )
    assert [m['occurrenceIndex'] for m in content_matches] == [0, 1, 2]
    assert data['totalMatches'] == 3
    assert data['totalChapters'] == 1


def test_multiple_notes_occurrences_are_multiple_results(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book(), name='Chapter C')
    chapter.notes_text = 'Talaktei background. More Talaktei lore here.'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    data = search(client, q='Talaktei').json
    notes_matches = sorted((m for m in data['matches'] if m['source'] == 'notes'), key=lambda m: m['occurrenceIndex'])
    assert [m['occurrenceIndex'] for m in notes_matches] == [0, 1]


def test_title_match_produces_exactly_one_title_result(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book(), name='The Talaktei Homeworld')
    chapter.content_html = '<p>Talaktei Talaktei Talaktei -- also in the title.</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    data = search(client, q='Talaktei').json
    title_matches = [m for m in data['matches'] if m['source'] == 'title']
    assert len(title_matches) == 1
    assert title_matches[0]['occurrenceIndex'] is None
    assert title_matches[0]['chapterId'] == str(chapter.id)


def test_title_content_and_notes_all_independently_appear(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book(), name='Talaktei Origins')
    chapter.content_html = '<p>Talaktei content.</p>'
    chapter.notes_text = 'Talaktei notes.'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    data = search(client, q='Talaktei').json
    sources = {m['source'] for m in data['matches']}
    assert sources == {'title', 'content', 'notes'}


def test_snippet_preserves_original_casing_and_has_no_html(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    chapter.content_html = '<p>The <strong>TaLaKtEi</strong> arrived among <em>strange</em> company.</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    data = search(client, q='talaktei').json
    content_matches = [m for m in data['matches'] if m['source'] == 'content']
    assert len(content_matches) == 1
    snippet = content_matches[0]['snippet']
    assert snippet['match'] == 'TaLaKtEi'
    assert '<' not in snippet['before'] and '<' not in snippet['after'] and '<' not in snippet['match']


def test_word_split_by_inline_formatting_is_still_searchable(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    chapter.content_html = '<p>The <strong>Talak</strong>tei arrived.</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    data = search(client, q='Talaktei').json
    content_matches = [m for m in data['matches'] if m['source'] == 'content']
    assert len(content_matches) == 1
    assert content_matches[0]['snippet']['match'] == 'Talaktei'


def test_list_content_is_searchable_without_injected_markers(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    chapter.content_html = '<ul><li>Talaktei item one</li><li>Talaktei item two</li></ul>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    data = search(client, q='Talaktei').json
    content_matches = [m for m in data['matches'] if m['source'] == 'content']
    assert len(content_matches) == 2
    for m in content_matches:
        assert '•' not in m['snippet']['before'] + m['snippet']['match'] + m['snippet']['after']


# ------------------------------------------------------- literal semantics --

def test_stop_word_is_searchable(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    chapter.content_html = '<p>To be or not to be, that is the question.</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    data = search(client, q='the').json
    assert any(m['source'] == 'content' for m in data['matches'])


def test_punctuation_containing_query_matches_literally(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    chapter.content_html = "<p>She said don't go, and he wrote C++ code that day.</p>"
    db.session.commit()

    client = app.test_client()
    login(client, user)
    assert any(m['source'] == 'content' for m in search(client, q="don't").json['matches'])
    assert any(m['source'] == 'content' for m in search(client, q='C++').json['matches'])


def test_regex_special_characters_do_not_crash_and_match_literally(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    chapter.content_html = '<p>Formula: (a+b)*[c.d] matches literally here.</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    for q in ['(a+b)', '[c.d]', '.*+?^$(){}|[]\\', '((((']:
        resp = search(client, q=q)
        assert resp.status_code == 200
    assert any(m['source'] == 'content' for m in search(client, q='(a+b)*[c.d]').json['matches'])


def test_mixed_casing_query_matches(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    chapter.content_html = '<p>The GALIDEN homeworld was vast.</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    assert any(m['source'] == 'content' for m in search(client, q='gAlIdEn').json['matches'])


def test_em_dash_is_searchable(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    chapter.content_html = '<p>The war ended — quietly, at last.</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    assert any(m['source'] == 'content' for m in search(client, q='—').json['matches'])


# --------------------------------------------------------------- permissions --

def test_owned_chapter_searchable(app, user, make_book, make_chapter):
    make_chapter(folder=make_book(), name='OwnedUniqueTerm12345')
    client = app.test_client()
    login(client, user)
    data = search(client, q='OwnedUniqueTerm12345').json
    assert data['totalChapters'] == 1


def test_book_share_chapter_searchable(app, cleanup, user, make_book, make_chapter):
    collaborator = make_collaborator(cleanup)
    book = make_book(name='Shared Book Search')
    make_chapter(folder=book, name='BookShareUniqueTerm')
    db.session.add(ResourceShare(folder_id=book.id, user_id=collaborator.id, role=ShareRole.viewer))
    db.session.commit()

    client = app.test_client()
    login(client, collaborator)
    data = search(client, q='BookShareUniqueTerm').json
    assert data['totalChapters'] == 1


def test_folder_share_descendants_searchable(app, cleanup, user, make_book, make_folder, make_chapter):
    collaborator = make_collaborator(cleanup)
    book = make_book(name='Folder Share Search')
    folder = make_folder(book, name='Shared Sub')
    make_chapter(folder=folder, name='FolderShareUniqueTerm')
    db.session.add(ResourceShare(folder_id=folder.id, user_id=collaborator.id, role=ShareRole.viewer))
    db.session.commit()

    client = app.test_client()
    login(client, collaborator)
    data = search(client, q='FolderShareUniqueTerm').json
    assert data['totalChapters'] == 1


def test_direct_chapter_share_and_its_descendants_searchable(app, cleanup, user, make_book, make_chapter):
    collaborator = make_collaborator(cleanup)
    book = make_book(name='Chapter Share Search')
    parent = make_chapter(folder=book, name='ChapterShareUniqueTerm')
    child = make_chapter(parent_chapter=parent, name='NestedUniqueTerm')
    db.session.add(ResourceShare(chapter_id=parent.id, user_id=collaborator.id, role=ShareRole.viewer))
    db.session.commit()

    client = app.test_client()
    login(client, collaborator)
    assert search(client, q='ChapterShareUniqueTerm').json['totalChapters'] == 1
    assert search(client, q='NestedUniqueTerm').json['totalChapters'] == 1


def test_inaccessible_chapter_excluded(app, cleanup, user, make_book, make_chapter):
    other_owner = make_collaborator(cleanup, name='otherowner')
    other_book = make_book(name='Not Mine', owner=other_owner)
    make_chapter(folder=other_book, name='InaccessibleUniqueTerm')

    client = app.test_client()
    login(client, user)
    data = search(client, q='InaccessibleUniqueTerm').json
    assert data['totalChapters'] == 0
    assert data['matches'] == []


def test_inaccessible_folder_scope_is_unavailable(app, cleanup, user, make_book, make_folder):
    other_owner = make_collaborator(cleanup, name='otherowner2')
    other_book = make_book(name='Not Mine 2', owner=other_owner)
    other_folder = make_folder(other_book, name='Not Mine Folder')

    client = app.test_client()
    login(client, user)
    resp = search(client, q='anything', scopeType='folder', scopeId=str(other_folder.id))
    assert resp.status_code == 404


def test_inaccessible_book_scope_is_unavailable(app, cleanup, user, make_book):
    other_owner = make_collaborator(cleanup, name='otherowner3')
    other_book = make_book(name='Not Mine 3', owner=other_owner)

    client = app.test_client()
    login(client, user)
    resp = search(client, q='anything', scopeType='book', scopeId=str(other_book.id))
    assert resp.status_code == 404


def test_narrow_share_does_not_expose_inaccessible_ancestor_scope(
    app, cleanup, user, make_book, make_folder, make_chapter,
):
    collaborator = make_collaborator(cleanup, name='narrow')
    book = make_book(name='Narrow Ancestor Book')
    folder = make_folder(book, name='Inaccessible Ancestor Folder')
    chapter = make_chapter(folder=folder, name='NarrowShareUniqueTerm')
    db.session.add(ResourceShare(chapter_id=chapter.id, user_id=collaborator.id, role=ShareRole.viewer))
    db.session.commit()

    client = app.test_client()
    login(client, collaborator)
    # Workspace search still finds the narrowly-shared chapter.
    assert search(client, q='NarrowShareUniqueTerm').json['totalChapters'] == 1
    # But neither the containing folder nor the book is a selectable scope.
    assert search(client, q='NarrowShareUniqueTerm', scopeType='folder', scopeId=str(folder.id)).status_code == 404
    assert search(client, q='NarrowShareUniqueTerm', scopeType='book', scopeId=str(book.id)).status_code == 404


# --------------------------------------------------------------------- scope --

def test_workspace_scope_finds_matches_across_accessible_books(app, user, make_book, make_chapter):
    make_chapter(folder=make_book(name='Book One WS'), name='WorkspaceScopeUniqueTerm A')
    make_chapter(folder=make_book(name='Book Two WS'), name='WorkspaceScopeUniqueTerm B')
    client = app.test_client()
    login(client, user)
    data = search(client, q='WorkspaceScopeUniqueTerm').json
    assert data['totalChapters'] == 2


def test_book_scope_excludes_other_books(app, user, make_book, make_chapter):
    book_a = make_book(name='Book Scope A')
    book_b = make_book(name='Book Scope B')
    make_chapter(folder=book_a, name='BookScopeUniqueTerm')
    make_chapter(folder=book_b, name='BookScopeUniqueTerm')

    client = app.test_client()
    login(client, user)
    data = search(client, q='BookScopeUniqueTerm', scopeType='book', scopeId=str(book_a.id)).json
    assert data['totalChapters'] == 1
    assert data['matches'][0]['bookId'] == str(book_a.id)


def test_folder_scope_includes_descendant_folders_and_nested_chapters(
    app, user, make_book, make_folder, make_chapter,
):
    book = make_book(name='Folder Scope Book')
    top = make_folder(book, name='Top')
    nested_folder = make_folder(top, name='Nested')
    other_folder = make_folder(book, name='Sibling')
    direct_chapter = make_chapter(folder=nested_folder, name='FolderScopeUniqueTerm direct')
    nested_chapter = make_chapter(parent_chapter=direct_chapter, name='FolderScopeUniqueTerm nested-chapter')
    make_chapter(folder=other_folder, name='FolderScopeUniqueTerm sibling')

    client = app.test_client()
    login(client, user)
    data = search(client, q='FolderScopeUniqueTerm', scopeType='folder', scopeId=str(top.id)).json
    chapter_ids = {m['chapterId'] for m in data['matches']}
    assert chapter_ids == {str(direct_chapter.id), str(nested_chapter.id)}


def test_scope_never_expands_permissions(app, cleanup, user, make_book, make_chapter):
    collaborator = make_collaborator(cleanup, name='scopelimited')
    book = make_book(name='Scope Never Expands')
    shared_chapter = make_chapter(folder=book, name='ScopeExpandUniqueTerm shared')
    make_chapter(folder=book, name='ScopeExpandUniqueTerm unshared')
    db.session.add(ResourceShare(chapter_id=shared_chapter.id, user_id=collaborator.id, role=ShareRole.viewer))
    db.session.commit()

    client = app.test_client()
    login(client, collaborator)
    # No book-level scope access -- can't even select the book as a scope.
    assert search(client, q='ScopeExpandUniqueTerm', scopeType='book', scopeId=str(book.id)).status_code == 404
    # Workspace search only surfaces the specifically shared chapter.
    data = search(client, q='ScopeExpandUniqueTerm').json
    assert data['totalChapters'] == 1
    assert data['matches'][0]['chapterId'] == str(shared_chapter.id)


# ---------------------------------------------------------------- pagination --

def test_pagination_limit_offset_deterministic_and_total_counts_correct(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book(), name='Pagination Chapter')
    chapter.content_html = '<p>' + ' '.join(['PagedTerm'] * 12) + '</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    page1 = search(client, q='PagedTerm', limit=5, offset=0).json
    page2 = search(client, q='PagedTerm', limit=5, offset=5).json
    page3 = search(client, q='PagedTerm', limit=5, offset=10).json

    assert page1['totalMatches'] == page2['totalMatches'] == page3['totalMatches'] == 12
    assert page1['totalChapters'] == 1
    assert [m['occurrenceIndex'] for m in page1['matches']] == [0, 1, 2, 3, 4]
    assert [m['occurrenceIndex'] for m in page2['matches']] == [5, 6, 7, 8, 9]
    assert [m['occurrenceIndex'] for m in page3['matches']] == [10, 11]
    assert page1['hasMore'] is True
    assert page2['hasMore'] is True
    assert page3['hasMore'] is False


def test_maximum_limit_is_enforced(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    chapter.content_html = '<p>' + ' '.join(['CapTerm'] * 150) + '</p>'
    db.session.commit()

    client = app.test_client()
    login(client, user)
    data = search(client, q='CapTerm', limit=10000).json
    assert data['limit'] == 100
    assert len(data['matches']) == 100
