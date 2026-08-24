"""Manual P0.10 clean-environment recovery harness.

Run through Docker Compose with DATABASE_URL pointed at disposable databases;
this is intentionally not pytest-collected. The three modes let the recovery
pass prove application-level portability and operational PostgreSQL cloning
without touching a developer's real workspace data.
"""
import argparse
import datetime
import io
import json
import uuid
from pathlib import Path

from bs4 import BeautifulSoup
from flask import g
from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import (
    Chapter,
    ChapterVersion,
    ChapterWritingActivity,
    Folder,
    Goal,
    GoalCadence,
    GoalPeriodHistory,
    GoalType,
    ResourceShare,
    ShareRole,
    User,
    UserSettings,
)
from services import html_to_text


PASSWORD = 'P0-Recovery-Password-123!'


def words_html(count, anchors=()):
    anchors = list(anchors)
    words = [f'w{i}' for i in range(count - len(anchors))]
    return '<p>' + ' '.join([*anchors, *words]) + '</p>'


def reference(target_type, target_id, label):
    return (
        f'<a href="calwriter://{target_type}/{target_id}" '
        f'data-calwriter-target-type="{target_type}" '
        f'data-calwriter-target-id="{target_id}">{label}</a>'
    )


def create_user(username, timezone):
    user = User(
        username=username,
        password_hash=generate_password_hash(PASSWORD),
        timezone=timezone,
    )
    db.session.add(user)
    db.session.flush()
    db.session.add(UserSettings(user_id=user.id))
    return user


def create_book(owner, name, position=0):
    book_id = uuid.uuid4()
    book = Folder(
        id=book_id,
        book_id=book_id,
        owner_id=owner.id,
        parent_id=None,
        name=name,
        position=position,
    )
    db.session.add(book)
    db.session.flush()
    return book


def create_folder(parent, name, position=0):
    folder = Folder(parent_id=parent.id, book_id=parent.book_id, name=name, position=position)
    db.session.add(folder)
    db.session.flush()
    return folder


def create_chapter(name, *, folder=None, parent=None, position=0):
    chapter = Chapter(
        name=name,
        folder_id=folder.id if folder is not None else None,
        parent_chapter_id=parent.id if parent is not None else None,
        book_id=folder.book_id if folder is not None else parent.book_id,
        position=position,
    )
    db.session.add(chapter)
    db.session.flush()
    return chapter


def login_client(user):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    g.pop('_login_user', None)
    g.pop('csrf_token', None)
    csrf = client.get('/api/auth/me').json['csrfToken']
    return client, {'X-CSRFToken': csrf}


def model_counts():
    return {
        'users': User.query.count(),
        'books': Folder.query.filter_by(parent_id=None).count(),
        'folders': Folder.query.count(),
        'chapters': Chapter.query.count(),
        'shares': ResourceShare.query.count(),
        'goals': Goal.query.count(),
        'goal_histories': GoalPeriodHistory.query.count(),
        'versions': ChapterVersion.query.count(),
        'writing_activity_rows': ChapterWritingActivity.query.count(),
    }


def seed_export(archive_path: Path, metadata_path: Path):
    owner = create_user('p010-owner', 'America/New_York')
    collaborator = create_user('p010-collaborator', 'Asia/Tokyo')
    viewer = create_user('p010-viewer', 'Europe/London')
    alpha = create_book(owner, 'Book Alpha', 0)
    beta = create_book(owner, 'Book Beta', 1)
    folder_a = create_folder(alpha, 'Folder A', 0)
    folder_b = create_folder(folder_a, 'Folder B', 0)
    folder_c = create_folder(alpha, 'Folder C', 1)
    chapter_1 = create_chapter('Chapter 1', folder=alpha, position=0)
    chapter_11 = create_chapter('Chapter 1.1', parent=chapter_1, position=0)
    chapter_12 = create_chapter('Chapter 1.2', parent=chapter_1, position=1)
    chapter_121 = create_chapter('Chapter 1.2.1', parent=chapter_12, position=0)
    chapter_2 = create_chapter('Chapter 2', folder=folder_a, position=0)
    chapter_3 = create_chapter('Chapter 3', folder=folder_b, position=0)
    chapter_4 = create_chapter('Chapter 4', folder=folder_c, position=0)
    chapter_5 = create_chapter('Chapter 5', folder=beta, position=0)
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
        chapter.notes_text = f'{chapter.name} notes'
    chapter_121.completed_at = datetime.datetime(2026, 8, 20, 12, tzinfo=datetime.timezone.utc)
    folder_b.show_book_color = False
    chapter_121.show_book_color = False
    alpha.color = '#123456'
    alpha.author = 'P0 Owner'
    alpha.description = 'Canonical recovery book'

    db.session.add_all([
        ResourceShare(folder_id=alpha.id, user_id=collaborator.id, role=ShareRole.editor),
        ResourceShare(folder_id=folder_c.id, user_id=viewer.id, role=ShareRole.viewer),
        ResourceShare(chapter_id=chapter_1.id, user_id=viewer.id, role=ShareRole.viewer),
        ChapterVersion(chapter_id=chapter_1.id, content_html='<p>Checkpoint one</p>'),
        ChapterVersion(chapter_id=chapter_1.id, content_html='<p>Checkpoint two</p>'),
        ChapterWritingActivity(
            user_id=owner.id, chapter_id=chapter_1.id,
            date=datetime.date(2026, 8, 24), hour_of_day=22,
            active_seconds=120, words_typed=40, words_pasted=10,
        ),
        ChapterWritingActivity(
            user_id=owner.id, chapter_id=chapter_12.id,
            date=datetime.date(2026, 8, 24), hour_of_day=23,
            active_seconds=180, words_typed=30, words_pasted=0,
        ),
        ChapterWritingActivity(
            user_id=collaborator.id, chapter_id=chapter_121.id,
            date=datetime.date(2026, 8, 25), hour_of_day=11,
            active_seconds=60, words_typed=20, words_pasted=5,
        ),
    ])
    word_goal = Goal(
        user_id=owner.id,
        folder_id=alpha.id,
        name='Owner-only folder goal',
        goal_type=GoalType.words,
        target=100,
        cadence=GoalCadence.weekly,
        start_date=datetime.date(2026, 8, 24),
        period_start=datetime.date(2026, 8, 24),
    )
    nested_goal = Goal(
        user_id=owner.id,
        chapter_id=chapter_1.id,
        name='Nested chapter goal',
        goal_type=GoalType.words,
        target=80,
        cadence=None,
        start_date=datetime.date(2026, 8, 24),
        end_date=datetime.date(2026, 8, 31),
        period_start=datetime.date(2026, 8, 24),
    )
    db.session.add_all([word_goal, nested_goal])
    db.session.flush()
    db.session.add_all([
        GoalPeriodHistory(
            goal_id=word_goal.id,
            period_start=datetime.date(2026, 8, 10),
            period_end=datetime.date(2026, 8, 16),
            target=100,
            current=90,
            achieved=False,
        ),
        GoalPeriodHistory(
            goal_id=word_goal.id,
            period_start=datetime.date(2026, 8, 17),
            period_end=datetime.date(2026, 8, 23),
            target=100,
            current=110,
            achieved=True,
        ),
    ])
    owner_settings = db.session.get(UserSettings, owner.id)
    owner_settings.book_order = [beta.id, alpha.id]
    owner_settings.open_book_ids = [alpha.id, beta.id]
    db.session.commit()

    client, _ = login_client(owner)
    export_response = client.get('/api/export')
    assert export_response.status_code == 200
    archive_path.write_bytes(export_response.data)
    metadata = {
        'counts': model_counts(),
        'ids': {
            'owner': str(owner.id),
            'collaborator': str(collaborator.id),
            'viewer': str(viewer.id),
            'alpha': str(alpha.id),
            'beta': str(beta.id),
            'chapter_1': str(chapter_1.id),
            'chapter_121': str(chapter_121.id),
        },
        'owner_workspace_words_typed': 70,
        'alpha_resource_words_typed': 90,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))
    print(json.dumps({'mode': 'seed-export', **metadata['counts']}, sort_keys=True))


def import_verify(archive_path: Path, metadata_path: Path):
    metadata = json.loads(metadata_path.read_text())
    owner = create_user('p010-restored-owner', 'UTC')
    db.session.commit()
    client, headers = login_client(owner)
    response = client.post(
        '/api/import',
        data={'file': (io.BytesIO(archive_path.read_bytes()), 'canonical.calwdb')},
        content_type='multipart/form-data',
        headers=headers,
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.json == {'imported': 2}
    alpha = Folder.query.filter_by(parent_id=None, name='Book Alpha').one()
    beta = Folder.query.filter_by(parent_id=None, name='Book Beta').one()
    chapter_1 = Chapter.query.filter_by(book_id=alpha.id, name='Chapter 1').one()
    chapter_121 = Chapter.query.filter_by(book_id=alpha.id, name='Chapter 1.2.1').one()
    folder_b = Folder.query.filter_by(book_id=alpha.id, name='Folder B').one()
    assert str(alpha.id) != metadata['ids']['alpha']
    assert Chapter.query.filter_by(book_id=alpha.id).count() == 7
    assert sum(len(html_to_text(ch.content_html).split()) for ch in Chapter.query.filter_by(book_id=alpha.id)) == 2800
    assert chapter_121.completed_at is not None
    assert chapter_121.show_book_color is False
    assert folder_b.show_book_color is False
    soup = BeautifulSoup(chapter_1.content_html, 'html.parser')
    targets = {
        (a['data-calwriter-target-type'], a.get_text()): a['data-calwriter-target-id']
        for a in soup.select('a[data-calwriter-target-id]')
    }
    assert targets[('chapter', 'nested-link')] == str(chapter_121.id)
    assert targets[('folder', 'folder-link')] == str(folder_b.id)
    assert targets[('book', 'book-link')] == str(beta.id)
    for (target_type, _), target_id in targets.items():
        assert client.get(f'/api/internal-references/{target_type}/{target_id}').status_code == 200
    assert ResourceShare.query.count() == 0
    assert Goal.query.count() == 0
    assert GoalPeriodHistory.query.count() == 0
    assert ChapterVersion.query.count() == 0
    assert ChapterWritingActivity.query.count() == 0
    stats = client.get(f'/api/folders/{alpha.id}/stats?days=0').json
    exact = client.get(f'/api/chapters/{chapter_1.id}/stats?days=0').json
    assert (stats['totalWords'], stats['chapterCount']) == (2800, 7)
    assert exact['totalWords'] == 100
    print(json.dumps({'mode': 'import-verify', 'result': 'PASS', **model_counts()}, sort_keys=True))


def clone_verify(metadata_path: Path):
    metadata = json.loads(metadata_path.read_text())
    assert model_counts() == metadata['counts']
    owner = db.session.get(User, uuid.UUID(metadata['ids']['owner']))
    collaborator = db.session.get(User, uuid.UUID(metadata['ids']['collaborator']))
    alpha = db.session.get(Folder, uuid.UUID(metadata['ids']['alpha']))
    chapter_1 = db.session.get(Chapter, uuid.UUID(metadata['ids']['chapter_1']))
    chapter_121 = db.session.get(Chapter, uuid.UUID(metadata['ids']['chapter_121']))
    assert owner and collaborator and alpha and chapter_1 and chapter_121
    assert owner.timezone == 'America/New_York'
    assert collaborator.timezone == 'Asia/Tokyo'
    assert chapter_121.parent_chapter.parent_chapter_id == chapter_1.id
    assert ResourceShare.query.filter_by(folder_id=alpha.id, user_id=collaborator.id).one().role == ShareRole.editor
    client, _ = login_client(owner)
    workspace = client.get('/api/stats?days=0').json
    alpha_stats = client.get(f'/api/folders/{alpha.id}/stats?days=0').json
    assert workspace['wordsTyped'] == metadata['owner_workspace_words_typed']
    assert alpha_stats['activity']['totals']['wordsTyped'] == metadata['alpha_resource_words_typed']
    assert len(alpha_stats['activity']['contributors']) == 2
    assert client.get(f'/api/internal-references/chapter/{chapter_121.id}').status_code == 200
    assert len(client.get(f'/api/chapters/{chapter_1.id}/versions').json) == 2
    goals = client.get('/api/goals').json
    assert len(goals) == 2
    history_goal = next(goal for goal in goals if goal['name'] == 'Owner-only folder goal')
    assert len(client.get(f"/api/goals/{history_goal['id']}/history").json['periods']) == 2
    login_response = app.test_client().post(
        '/api/auth/login', json={'username': owner.username, 'password': PASSWORD}
    )
    assert login_response.status_code == 200
    print(json.dumps({'mode': 'clone-verify', 'result': 'PASS', **model_counts()}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('seed-export', 'import-verify', 'clone-verify'))
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--metadata', type=Path, required=True)
    args = parser.parse_args()
    with app.app_context():
        if args.mode == 'seed-export':
            if args.archive is None:
                parser.error('--archive is required')
            seed_export(args.archive, args.metadata)
        elif args.mode == 'import-verify':
            if args.archive is None:
                parser.error('--archive is required')
            import_verify(args.archive, args.metadata)
        else:
            clone_verify(args.metadata)


if __name__ == '__main__':
    main()
