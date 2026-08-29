import datetime
import uuid

from flask import g

from extensions import db
from models import ChapterWritingActivity, ResourceShare, ShareRole, User


def login(client, user):
    with client.session_transaction() as session:
        session.clear()
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    # The suite's app_context fixture intentionally spans a whole test,
    # unlike production's request-scoped app context. Clear Flask-Login's
    # cached proxy when this test switches identities mid-test.
    g.pop('_login_user', None)


def make_collaborator(cleanup):
    collaborator = User(username=f'contributor-{uuid.uuid4().hex[:12]}', password_hash='x', is_admin=False)
    db.session.add(collaborator)
    db.session.commit()
    cleanup['users'].append(collaborator.id)
    return collaborator


def add_activity(user, chapter, *, typed, pasted, active, date=None, hour=12):
    db.session.add(ChapterWritingActivity(
        user_id=user.id,
        chapter_id=chapter.id,
        date=date or datetime.date.today(),
        hour_of_day=hour,
        words_typed=typed,
        words_pasted=pasted,
        active_seconds=active,
    ))
    db.session.commit()


def by_user(payload):
    return {row['userId']: row for row in payload['activity']['contributors']}


def test_shared_folder_stats_show_resource_totals_and_each_users_own_wpm(
    app, cleanup, user, make_book, make_folder, make_chapter,
):
    collaborator = make_collaborator(cleanup)
    book = make_book(name='Contribution Book')
    folder = make_folder(book, name='Shared Folder')
    chapter = make_chapter(folder=folder, name='Direct')
    nested = make_chapter(parent_chapter=chapter, name='Nested')
    add_activity(user, chapter, typed=120, pasted=60, active=360, hour=10)
    add_activity(collaborator, nested, typed=90, pasted=5, active=180, hour=11)
    share = ResourceShare(folder_id=folder.id, user_id=collaborator.id, role=ShareRole.viewer)
    db.session.add(share)
    db.session.commit()

    client = app.test_client()
    login(client, user)
    owner_stats = client.get(f'/api/folders/{folder.id}/stats?days=0')
    assert owner_stats.status_code == 200
    owner_stats = owner_stats.json
    assert owner_stats['activity']['totals'] == {
        'wordsTyped': 210, 'wordsPasted': 65, 'wordsDeleted': 0, 'wordsWritten': 210, 'activeSeconds': 540,
    }
    assert 'wpm' not in owner_stats['activity']['totals']
    assert 'wpm' not in owner_stats
    owner_rows = by_user(owner_stats)
    assert owner_rows[str(user.id)]['wpm'] == 20.0
    assert owner_rows[str(collaborator.id)]['wpm'] == 30.0
    assert owner_stats['activity']['mine'] == owner_rows[str(user.id)]

    collaborator_client = app.test_client()
    login(collaborator_client, collaborator)
    collaborator_stats = collaborator_client.get(f'/api/folders/{folder.id}/stats?days=0')
    assert collaborator_stats.status_code == 200
    collaborator_stats = collaborator_stats.json
    assert collaborator_stats['activity']['totals'] == owner_stats['activity']['totals']
    assert collaborator_stats['activity']['mine']['userId'] == str(collaborator.id)
    assert collaborator_stats['activity']['mine']['wpm'] == 30.0
    assert {row['userId'] for row in collaborator_stats['activity']['contributors']} == {
        str(user.id), str(collaborator.id),
    }

    # Removing access does not rewrite authorship. The owner still sees the
    # historical row; the former collaborator can no longer see the stats.
    db.session.delete(share)
    db.session.commit()
    login(client, user)
    after_unshare = client.get(f'/api/folders/{folder.id}/stats?days=0').json
    assert by_user(after_unshare)[str(collaborator.id)]['wordsTyped'] == 90
    former_collaborator_client = app.test_client()
    login(former_collaborator_client, collaborator)
    assert former_collaborator_client.get(f'/api/folders/{folder.id}/stats?days=0').status_code == 404


def test_chapter_contributions_are_exact_chapter_only(
    app, cleanup, user, make_book, make_chapter,
):
    collaborator = make_collaborator(cleanup)
    book = make_book(name='Exact Chapter Contributions')
    parent = make_chapter(folder=book, name='Parent')
    child = make_chapter(parent_chapter=parent, name='Child')
    add_activity(user, parent, typed=60, pasted=2, active=360, hour=9)
    add_activity(collaborator, parent, typed=30, pasted=3, active=60, hour=10)
    add_activity(collaborator, child, typed=500, pasted=50, active=600, hour=11)
    db.session.add(ResourceShare(chapter_id=parent.id, user_id=collaborator.id, role=ShareRole.viewer))
    db.session.commit()

    client = app.test_client()
    login(client, user)
    stats = client.get(f'/api/chapters/{parent.id}/stats?days=0').json
    assert stats['activity']['totals'] == {
        'wordsTyped': 90, 'wordsPasted': 5, 'wordsDeleted': 0, 'wordsWritten': 90, 'activeSeconds': 420,
    }
    rows = by_user(stats)
    assert rows[str(user.id)]['wpm'] == 10.0
    assert rows[str(collaborator.id)]['wpm'] == 30.0

    collaborator_client = app.test_client()
    login(collaborator_client, collaborator)
    assert collaborator_client.get(f'/api/chapters/{parent.id}/stats?days=0').status_code == 200


def test_workspace_behavioral_stats_exclude_collaborator_activity(
    app, cleanup, user, make_book, make_chapter,
):
    collaborator = make_collaborator(cleanup)
    book = make_book(name='Personal Workspace Stats')
    mine = make_chapter(folder=book, name='My busiest')
    theirs = make_chapter(folder=book, name='Collaborator busiest')
    db.session.add(ResourceShare(folder_id=book.id, user_id=collaborator.id, role=ShareRole.viewer))
    db.session.commit()
    add_activity(user, mine, typed=100, pasted=4, active=600, hour=8)
    add_activity(
        collaborator,
        theirs,
        typed=1000,
        pasted=400,
        active=1200,
        date=datetime.date.today() - datetime.timedelta(days=1),
        hour=9,
    )

    client = app.test_client()
    login(client, user)
    stats = client.get('/api/stats?days=0').json
    assert (stats['wordsTyped'], stats['wordsPasted'], stats['totalActiveSeconds']) == (100, 4, 600)
    assert stats['avgWpm'] == 10.0
    assert stats['weekOverWeekWords']['thisWeek'] == 100
    assert stats['busiestResource']['chapterId'] == str(mine.id)
    assert sum(bucket['activeSeconds'] for bucket in stats['heatmap']) == 600
    assert stats['streak']['current'] == 1
