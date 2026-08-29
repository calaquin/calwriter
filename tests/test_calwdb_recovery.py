import datetime
import io
import json
import uuid
import zipfile

from bs4 import BeautifulSoup
from flask import g

from extensions import db
from models import (
    Chapter,
    ChapterVersion,
    ChapterWritingActivity,
    Folder,
    Goal,
    GoalCadence,
    GoalType,
    ResourceShare,
    ShareRole,
    User,
    UserSettings,
)


def authenticated_client(app, user):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    g.pop('_login_user', None)
    g.pop('csrf_token', None)
    csrf_token = client.get('/api/auth/me').json['csrfToken']
    return client, {'X-CSRFToken': csrf_token}


def words_html(count, anchors=()):
    anchors = list(anchors)
    remaining = [f'w{i}' for i in range(count - len(anchors))]
    return '<p>' + ' '.join([*anchors, *remaining]) + '</p>'


def reference(target_type, target_id, label):
    return (
        f'<a href="calwriter://{target_type}/{target_id}" '
        f'data-calwriter-target-type="{target_type}" '
        f'data-calwriter-target-id="{target_id}">{label}</a>'
    )


def archive_bytes(payload):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('data.json', json.dumps(payload))
    output.seek(0)
    return output


def test_calwdb_round_trip_preserves_nested_books_and_remaps_internal_references(
    app, cleanup, user, make_book, make_folder, make_chapter,
):
    collaborator = User(username=f'recovery-b-{uuid.uuid4().hex[:10]}', password_hash='x', timezone='Asia/Tokyo')
    viewer = User(username=f'recovery-c-{uuid.uuid4().hex[:10]}', password_hash='x', timezone='Europe/London')
    db.session.add_all([collaborator, viewer])
    db.session.commit()
    cleanup['users'].extend([collaborator.id, viewer.id])

    alpha = make_book(name='Book Alpha')
    alpha.description = 'Alpha description'
    alpha.author = 'Primary Writer'
    alpha.color = '#123456'
    alpha.show_book_color = False
    chapter_1 = make_chapter(folder=alpha, name='Chapter 1')
    chapter_11 = make_chapter(parent_chapter=chapter_1, name='Chapter 1.1')
    chapter_12 = make_chapter(parent_chapter=chapter_1, name='Chapter 1.2')
    chapter_121 = make_chapter(parent_chapter=chapter_12, name='Chapter 1.2.1')
    folder_a = make_folder(alpha, name='Folder A')
    chapter_2 = make_chapter(folder=folder_a, name='Chapter 2')
    folder_b = make_folder(folder_a, name='Folder B')
    chapter_3 = make_chapter(folder=folder_b, name='Chapter 3')
    folder_c = make_folder(alpha, name='Folder C')
    chapter_4 = make_chapter(folder=folder_c, name='Chapter 4')
    beta = make_book(name='Book Beta')
    chapter_5 = make_chapter(folder=beta, name='Chapter 5')

    anchors = [
        reference('chapter', chapter_11.id, 'chapter-link'),
        reference('chapter', chapter_121.id, 'nested-link'),
        reference('folder', folder_b.id, 'folder-link'),
        reference('book', beta.id, 'book-link'),
    ]
    chapters = [chapter_1, chapter_11, chapter_12, chapter_121, chapter_2, chapter_3, chapter_4, chapter_5]
    for chapter, count in zip(chapters, (100, 200, 300, 400, 500, 600, 700, 800)):
        chapter.content_html = words_html(count, anchors if chapter is chapter_1 else ())
        chapter.description = f'{chapter.name} description'
        chapter.notes_text = f'{chapter.name} private notes'
    chapter_121.completed_at = datetime.datetime(2026, 8, 20, 12, tzinfo=datetime.timezone.utc)
    chapter_121.show_book_color = False
    folder_b.show_book_color = False

    db.session.add_all([
        ResourceShare(folder_id=alpha.id, user_id=collaborator.id, role=ShareRole.editor),
        ResourceShare(folder_id=folder_c.id, user_id=viewer.id, role=ShareRole.viewer),
        ResourceShare(chapter_id=chapter_1.id, user_id=viewer.id, role=ShareRole.viewer),
        ChapterVersion(chapter_id=chapter_1.id, content_html='<p>Old checkpoint</p>'),
        ChapterWritingActivity(
            user_id=user.id,
            chapter_id=chapter_1.id,
            date=datetime.date(2026, 8, 24),
            hour_of_day=10,
            active_seconds=120,
            words_typed=40,
            words_pasted=10,
        ),
        Goal(
            user_id=user.id,
            folder_id=alpha.id,
            name='Portable contract boundary',
            goal_type=GoalType.words,
            target=1000,
            cadence=GoalCadence.weekly,
            start_date=datetime.date(2026, 8, 24),
            period_start=datetime.date(2026, 8, 24),
        ),
    ])
    db.session.commit()

    client, headers = authenticated_client(app, user)
    exported = client.get('/api/export')
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.data)) as archive:
        payload = json.loads(archive.read('data.json'))
    assert payload['version'] == '4.0'
    assert {'users', 'shares', 'goals', 'versions', 'writing_activity'}.isdisjoint(payload)

    restored = client.post(
        '/api/import',
        data={'file': (io.BytesIO(exported.data), 'recovery.calwdb')},
        content_type='multipart/form-data',
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json == {'imported': 2}

    imported_alpha = Folder.query.filter_by(parent_id=None, name='Book Alpha (2)').one()
    imported_beta = Folder.query.filter_by(parent_id=None, name='Book Beta (2)').one()
    cleanup['books'].extend([imported_alpha.id, imported_beta.id])
    assert imported_alpha.id != alpha.id
    assert (imported_alpha.description, imported_alpha.author, imported_alpha.color) == (
        'Alpha description', 'Primary Writer', '#123456',
    )
    assert imported_alpha.show_book_color is False

    imported_folder_b = Folder.query.filter_by(book_id=imported_alpha.id, name='Folder B').one()
    imported_chapter_1 = Chapter.query.filter_by(book_id=imported_alpha.id, name='Chapter 1').one()
    imported_chapter_11 = Chapter.query.filter_by(book_id=imported_alpha.id, name='Chapter 1.1').one()
    imported_chapter_12 = Chapter.query.filter_by(book_id=imported_alpha.id, name='Chapter 1.2').one()
    imported_chapter_121 = Chapter.query.filter_by(book_id=imported_alpha.id, name='Chapter 1.2.1').one()
    assert imported_chapter_11.parent_chapter_id == imported_chapter_1.id
    assert imported_chapter_12.parent_chapter_id == imported_chapter_1.id
    assert imported_chapter_121.parent_chapter_id == imported_chapter_12.id
    assert imported_chapter_121.completed_at == chapter_121.completed_at
    assert imported_chapter_121.show_book_color is False
    assert imported_folder_b.show_book_color is False
    assert imported_chapter_121.notes_text == 'Chapter 1.2.1 private notes'

    soup = BeautifulSoup(imported_chapter_1.content_html, 'html.parser')
    references = {
        anchor['data-calwriter-target-type']: anchor['data-calwriter-target-id']
        for anchor in soup.select('a[data-calwriter-target-id]')
    }
    chapter_reference_ids = {
        anchor['data-calwriter-target-id']
        for anchor in soup.select('a[data-calwriter-target-type="chapter"]')
    }
    assert chapter_reference_ids == {str(imported_chapter_11.id), str(imported_chapter_121.id)}
    assert references['folder'] == str(imported_folder_b.id)
    assert references['book'] == str(imported_beta.id)
    for anchor in soup.select('a[data-calwriter-target-id]'):
        target_type = anchor['data-calwriter-target-type']
        target_id = anchor['data-calwriter-target-id']
        assert anchor['href'] == f'calwriter://{target_type}/{target_id}'
        assert client.get(f'/api/internal-references/{target_type}/{target_id}').status_code == 200

    # .calwdb is portable book content, not a multi-user/telemetry clone.
    assert ResourceShare.query.filter_by(folder_id=imported_alpha.id).count() == 0
    assert ChapterVersion.query.filter_by(chapter_id=imported_chapter_1.id).count() == 0
    assert ChapterWritingActivity.query.filter_by(chapter_id=imported_chapter_1.id).count() == 0
    assert Goal.query.filter_by(folder_id=imported_alpha.id).count() == 0

    book_stats = client.get(f'/api/folders/{imported_alpha.id}/stats?days=0').json
    parent_stats = client.get(f'/api/chapters/{imported_chapter_1.id}/stats?days=0').json
    assert (book_stats['totalWords'], book_stats['chapterCount']) == (2800, 7)
    assert book_stats['activity']['totals'] == {
        'wordsTyped': 0, 'wordsPasted': 0, 'wordsDeleted': 0, 'wordsWritten': 0, 'activeSeconds': 0,
    }
    assert parent_stats['totalWords'] == 100


def test_invalid_deep_calwdb_import_is_atomic(app, cleanup, user):
    client, headers = authenticated_client(app, user)
    before = Folder.query.filter_by(parent_id=None, owner_id=user.id).count()
    assert db.session.get(UserSettings, user.id) is None
    too_deep = {'name': 'Level 0', 'children': []}
    node = too_deep
    for depth in range(1, 7):
        child = {'name': f'Level {depth}', 'children': []}
        node['children'].append(child)
        node = child
    payload = {
        'version': '3.0',
        'books': [
            {'name': 'Would otherwise import', 'folders': [], 'chapters': []},
            {'name': 'Invalid deep book', 'folders': [], 'chapters': [too_deep]},
        ],
    }

    response = client.post(
        '/api/import',
        data={'file': (archive_bytes(payload), 'too-deep.calwdb')},
        content_type='multipart/form-data',
        headers=headers,
    )
    assert response.status_code == 400
    assert 'nested more than' in response.json['error']
    assert Folder.query.filter_by(parent_id=None, owner_id=user.id).count() == before
    assert db.session.get(UserSettings, user.id) is None


# ------------------------------------------------------- P1.2 book types/journal --

def test_v4_export_preserves_book_type_and_journal_metadata(app, cleanup, user, make_book):
    from services import journal_write_today

    book = make_book(name='Journal Export Book')
    book.book_type = 'journal'
    db.session.commit()
    chapter, _ = journal_write_today(book)
    db.session.commit()
    month_folder = db.session.get(Folder, chapter.folder_id)
    year_folder = db.session.get(Folder, month_folder.parent_id)

    client, headers = authenticated_client(app, user)
    exported = client.get('/api/export')
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.data)) as archive:
        payload = json.loads(archive.read('data.json'))
    assert payload['version'] == '4.0'

    book_data = next(b for b in payload['books'] if b['source_id'] == str(book.id))
    assert book_data['book_type'] == 'journal'
    year_data = next(f for f in book_data['folders'] if f['source_id'] == str(year_folder.id))
    assert (year_data['journal_year'], year_data['journal_month']) == (year_folder.journal_year, None)
    month_data = next(f for f in year_data['folders'] if f['source_id'] == str(month_folder.id))
    assert (month_data['journal_year'], month_data['journal_month']) == (year_folder.journal_year, month_folder.journal_month)
    day_data = next(c for c in month_data['chapters'] if c['source_id'] == str(chapter.id))
    assert day_data['journal_date'] == chapter.journal_date.isoformat()


def test_v4_import_restores_book_type_and_journal_metadata(app, cleanup, user, make_book):
    from services import journal_write_today

    book = make_book(name='Journal Round Trip Book')
    book.book_type = 'journal'
    db.session.commit()
    chapter, _ = journal_write_today(book)
    db.session.commit()

    client, headers = authenticated_client(app, user)
    exported = client.get('/api/export')
    restored = client.post(
        '/api/import',
        data={'file': (io.BytesIO(exported.data), 'journal.calwdb')},
        content_type='multipart/form-data',
        headers=headers,
    )
    assert restored.status_code == 200
    books_after = {b.name: b for b in Folder.query.filter_by(parent_id=None, owner_id=user.id).all()}
    imported_book = next(b for name, b in books_after.items() if name.startswith('Journal Round Trip Book') and b.id != book.id)
    cleanup['books'].append(imported_book.id)
    assert imported_book.book_type == 'journal'

    imported_year = Folder.query.filter_by(book_id=imported_book.id, journal_month=None).filter(Folder.journal_year.isnot(None)).one()
    imported_month = Folder.query.filter_by(book_id=imported_book.id).filter(Folder.journal_month.isnot(None)).one()
    imported_chapter = Chapter.query.filter_by(book_id=imported_book.id).filter(Chapter.journal_date.isnot(None)).one()
    assert imported_month.parent_id == imported_year.id
    assert imported_chapter.journal_date == chapter.journal_date


def test_old_v3_archive_imports_as_general_with_null_journal_metadata(app, cleanup, user):
    payload = {
        'version': '3.0',
        'books': [{
            'name': f'Legacy V3 Book {uuid.uuid4().hex[:6]}',
            'folders': [{'name': 'Sub', 'folders': [], 'chapters': []}],
            'chapters': [{'name': 'August 29, 2026', 'content_html': '<p>Not actually a journal entry.</p>', 'children': []}],
        }],
    }
    client, headers = authenticated_client(app, user)
    response = client.post(
        '/api/import',
        data={'file': (archive_bytes(payload), 'legacy.calwdb')},
        content_type='multipart/form-data',
        headers=headers,
    )
    assert response.status_code == 200
    book = Folder.query.filter(Folder.parent_id.is_(None), Folder.owner_id == user.id, Folder.name.like('Legacy V3 Book%')).one()
    cleanup['books'].append(book.id)
    assert book.book_type == 'general'
    sub = Folder.query.filter_by(parent_id=book.id).one()
    assert sub.journal_year is None and sub.journal_month is None
    chapter = Chapter.query.filter_by(book_id=book.id).one()
    # Not inferred from the "August 29, 2026"-shaped name -- only explicit metadata has Journal semantics.
    assert chapter.journal_date is None


def test_malformed_journal_month_without_year_rejected_atomically(app, cleanup, user):
    client, headers = authenticated_client(app, user)
    before = Folder.query.filter_by(parent_id=None, owner_id=user.id).count()
    payload = {
        'version': '4.0',
        'books': [{
            'name': 'Malformed Month Book', 'book_type': 'journal',
            'folders': [{'name': 'August', 'journal_month': 8, 'folders': [], 'chapters': []}],
            'chapters': [],
        }],
    }
    response = client.post(
        '/api/import',
        data={'file': (archive_bytes(payload), 'bad-month.calwdb')},
        content_type='multipart/form-data',
        headers=headers,
    )
    assert response.status_code == 400
    assert Folder.query.filter_by(parent_id=None, owner_id=user.id).count() == before


def test_malformed_book_type_rejected_atomically(app, cleanup, user):
    client, headers = authenticated_client(app, user)
    before = Folder.query.filter_by(parent_id=None, owner_id=user.id).count()
    payload = {'version': '4.0', 'books': [{'name': 'Bad Type Book', 'book_type': 'saga', 'folders': [], 'chapters': []}]}
    response = client.post(
        '/api/import',
        data={'file': (archive_bytes(payload), 'bad-type.calwdb')},
        content_type='multipart/form-data',
        headers=headers,
    )
    assert response.status_code == 400
    assert Folder.query.filter_by(parent_id=None, owner_id=user.id).count() == before


def test_duplicate_journal_dates_within_one_book_rejected_atomically(app, cleanup, user):
    client, headers = authenticated_client(app, user)
    before = Folder.query.filter_by(parent_id=None, owner_id=user.id).count()
    payload = {
        'version': '4.0',
        'books': [
            {'name': 'Would Otherwise Import', 'folders': [], 'chapters': []},
            {
                'name': 'Duplicate Date Book', 'book_type': 'journal',
                'folders': [],
                'chapters': [
                    {'name': 'Entry A', 'journal_date': '2026-08-29', 'children': []},
                    {'name': 'Entry B', 'journal_date': '2026-08-29', 'children': []},
                ],
            },
        ],
    }
    response = client.post(
        '/api/import',
        data={'file': (archive_bytes(payload), 'dup-date.calwdb')},
        content_type='multipart/form-data',
        headers=headers,
    )
    assert response.status_code == 400
    # Atomic across the WHOLE archive -- the first (individually valid) book
    # must not have been created just because a later book failed.
    assert Folder.query.filter_by(parent_id=None, owner_id=user.id).count() == before
    assert not Folder.query.filter_by(parent_id=None, owner_id=user.id, name='Would Otherwise Import').first()
