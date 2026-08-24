import uuid

from extensions import db
from models import Chapter, ResourceShare, ShareRole, User
from services import sanitize_html


def login(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True


def test_sanitizer_preserves_typed_uuid_reference_but_rejects_script_urls():
    target_id = uuid.uuid4()
    cleaned = sanitize_html(
        f'<a href="calwriter://chapter/{target_id}" '
        f'data-calwriter-target-type="chapter" data-calwriter-target-id="{target_id}">Target</a>'
        '<a href="javascript:alert(1)">Unsafe</a>'
    )
    assert f'href="calwriter://chapter/{target_id}"' in cleaned
    assert 'data-calwriter-target-type="chapter"' in cleaned
    assert f'data-calwriter-target-id="{target_id}"' in cleaned
    assert 'javascript:' not in cleaned


def test_reference_survives_cross_book_move_rename_and_target_delete(
    app, user, make_book, make_chapter,
):
    book_a = make_book(name='Book A')
    book_b = make_book(name='Book B')
    source = make_chapter(folder=book_a, name='Source')
    target = make_chapter(folder=book_a, name='Original target')
    source.content_html = sanitize_html(
        f'<p>See <a href="calwriter://chapter/{target.id}" '
        f'data-calwriter-target-type="chapter" data-calwriter-target-id="{target.id}">this chapter</a>.</p>'
    )
    db.session.commit()

    client = app.test_client()
    login(client, user)
    response = client.get(f'/api/internal-references/chapter/{target.id}')
    assert response.status_code == 200
    assert response.json['route'] == f'/chapters/{target.id}'

    # Identity, not hierarchy or display name, drives resolution.
    target.folder_id = book_b.id
    target.book_id = book_b.id
    target.name = 'Renamed after moving'
    db.session.commit()
    response = client.get(f'/api/internal-references/chapter/{target.id}')
    assert response.status_code == 200
    assert response.json['name'] == 'Renamed after moving'
    assert response.json['route'] == f'/chapters/{target.id}'

    target_id = target.id
    db.session.delete(target)
    db.session.commit()
    response = client.get(f'/api/internal-references/chapter/{target_id}')
    assert response.status_code == 404
    assert response.json == {'error': 'Reference unavailable'}
    assert str(target_id) in db.session.get(Chapter, source.id).content_html


def test_picker_and_resolver_support_book_folder_and_chapter(
    app, user, make_book, make_folder, make_chapter,
):
    book = make_book(name='Reference book')
    folder = make_folder(book, name='Reference folder')
    chapter = make_chapter(folder=folder, name='Reference chapter')
    client = app.test_client()
    login(client, user)

    response = client.get('/api/internal-references')
    assert response.status_code == 200
    by_id = {item['targetId']: item for item in response.json}
    assert by_id[str(book.id)]['targetType'] == 'book'
    assert by_id[str(folder.id)]['targetType'] == 'folder'
    assert by_id[str(chapter.id)]['targetType'] == 'chapter'

    expected = [
        ('book', book.id, f'/folders/{book.id}'),
        ('folder', folder.id, f'/folders/{folder.id}'),
        ('chapter', chapter.id, f'/chapters/{chapter.id}'),
    ]
    for target_type, target_id, route in expected:
        resolved = client.get(f'/api/internal-references/{target_type}/{target_id}')
        assert resolved.status_code == 200
        assert resolved.json['route'] == route


def test_resolver_does_not_distinguish_private_missing_or_mistyped_targets(
    app, cleanup, user, make_book, make_chapter,
):
    other = User(username=f'private-{uuid.uuid4().hex[:12]}', password_hash='x', is_admin=False)
    db.session.add(other)
    db.session.commit()
    cleanup['users'].append(other.id)
    private_book = make_book(name='Private book', owner=other)
    private_chapter = make_chapter(folder=private_book, name='Private chapter')

    client = app.test_client()
    login(client, user)
    paths = [
        f'/api/internal-references/chapter/{private_chapter.id}',
        f'/api/internal-references/chapter/{uuid.uuid4()}',
        f'/api/internal-references/folder/{private_book.id}',
    ]
    responses = [client.get(path) for path in paths]
    assert [response.status_code for response in responses] == [404, 404, 404]
    assert [response.json for response in responses] == [
        {'error': 'Reference unavailable'},
        {'error': 'Reference unavailable'},
        {'error': 'Reference unavailable'},
    ]


def test_picker_includes_narrow_shared_subtree_without_private_ancestors(
    app, cleanup, user, make_book, make_folder, make_chapter,
):
    other = User(username=f'sharer-{uuid.uuid4().hex[:12]}', password_hash='x', is_admin=False)
    db.session.add(other)
    db.session.commit()
    cleanup['users'].append(other.id)
    private_book = make_book(name='Containing book', owner=other)
    private_folder = make_folder(private_book, name='Private folder')
    shared_root = make_chapter(folder=private_folder, name='Shared root')
    shared_child = make_chapter(parent_chapter=shared_root, name='Shared child')
    db.session.add(ResourceShare(chapter_id=shared_root.id, user_id=user.id, role=ShareRole.viewer))
    db.session.commit()

    client = app.test_client()
    login(client, user)
    response = client.get('/api/internal-references')
    assert response.status_code == 200
    by_id = {item['targetId']: item for item in response.json}
    assert by_id[str(shared_root.id)]['depth'] == 0
    assert by_id[str(shared_child.id)]['depth'] == 1
    assert str(private_book.id) not in by_id
    assert str(private_folder.id) not in by_id
