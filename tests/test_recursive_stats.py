import datetime
import uuid

from extensions import db
from models import ChapterWritingActivity, User
from services import chapter_ids_under_folder, writing_activity_totals


def login(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True


def words(count):
    return '<p>' + ' '.join(f'w{i}' for i in range(count)) + '</p>'


def build_canonical_tree(user, make_book, make_folder, make_chapter):
    book = make_book(name='Recursive Stats Book')
    root = make_chapter(folder=book, name='Chapter Root')
    folder_a = make_folder(book, name='Folder A')
    chapter_a = make_chapter(folder=folder_a, name='Chapter A')
    folder_b = make_folder(folder_a, name='Folder B')
    chapter_b = make_chapter(folder=folder_b, name='Chapter B')
    chapter_c = make_chapter(folder=folder_b, name='Chapter C')
    chapter_c1 = make_chapter(parent_chapter=chapter_c, name='Subchapter C.1')

    chapters = [root, chapter_a, chapter_b, chapter_c, chapter_c1]
    counts = [50, 100, 200, 300, 400]
    for index, (chapter, count) in enumerate(zip(chapters, counts), start=1):
        chapter.content_html = words(count)
        chapter.version_count = index
    chapter_c.completed_at = datetime.datetime.now(datetime.timezone.utc)
    chapter_c1.completed_at = datetime.datetime.now(datetime.timezone.utc)
    db.session.commit()

    today = datetime.date.today()
    for index, (chapter, count) in enumerate(zip(chapters, counts), start=1):
        typed = count // 10
        db.session.add(ChapterWritingActivity(
            user_id=user.id,
            chapter_id=chapter.id,
            date=today,
            hour_of_day=10 + index,
            active_seconds=typed * 6,  # exactly 10 active WPM for every chapter and aggregate
            words_typed=typed,
            words_pasted=index,
        ))
    db.session.commit()
    return {
        'book': book,
        'folderA': folder_a,
        'folderB': folder_b,
        'root': root,
        'chapterA': chapter_a,
        'chapterB': chapter_b,
        'chapterC': chapter_c,
        'chapterC1': chapter_c1,
    }


def test_canonical_recursive_scope_ids_include_nested_folders_and_subchapters(
    user, make_book, make_folder, make_chapter,
):
    tree = build_canonical_tree(user, make_book, make_folder, make_chapter)
    assert set(chapter_ids_under_folder(tree['folderB'].id)) == {
        tree['chapterB'].id, tree['chapterC'].id, tree['chapterC1'].id,
    }
    assert set(chapter_ids_under_folder(tree['folderA'].id)) == {
        tree['chapterA'].id, tree['chapterB'].id, tree['chapterC'].id, tree['chapterC1'].id,
    }
    assert set(chapter_ids_under_folder(tree['book'].id)) == {
        tree['root'].id, tree['chapterA'].id, tree['chapterB'].id,
        tree['chapterC'].id, tree['chapterC1'].id,
    }


def test_book_and_folder_stats_recursively_aggregate_every_dimension(
    app, user, make_book, make_folder, make_chapter,
):
    tree = build_canonical_tree(user, make_book, make_folder, make_chapter)
    client = app.test_client()
    login(client, user)

    book = client.get(f"/api/folders/{tree['book'].id}/stats?days=0").json
    folder_a = client.get(f"/api/folders/{tree['folderA'].id}/stats?days=0").json
    folder_b = client.get(f"/api/folders/{tree['folderB'].id}/stats?days=0").json

    assert (book['totalWords'], folder_a['totalWords'], folder_b['totalWords']) == (1050, 1000, 900)
    assert (book['chapterCount'], folder_a['chapterCount'], folder_b['chapterCount']) == (5, 4, 3)
    assert (book['completedChapterCount'], folder_a['completedChapterCount'], folder_b['completedChapterCount']) == (2, 2, 2)
    assert (book['revisionCount'], folder_a['revisionCount'], folder_b['revisionCount']) == (15, 14, 12)
    assert tuple(stats['activity']['totals']['wordsTyped'] for stats in (book, folder_a, folder_b)) == (105, 100, 90)
    assert tuple(stats['activity']['totals']['wordsPasted'] for stats in (book, folder_a, folder_b)) == (15, 14, 12)
    assert tuple(stats['activity']['totals']['activeSeconds'] for stats in (book, folder_a, folder_b)) == (630, 600, 540)
    assert tuple(stats['activity']['mine']['wpm'] for stats in (book, folder_a, folder_b)) == (10.0, 10.0, 10.0)

    # Spread remains an explicitly direct-sibling comparison: Folder B's
    # 400-word nested C.1 must aggregate into totals, but not distort the
    # direct Chapter B/Chapter C min/avg/max comparison.
    assert folder_b['wordCountSpread'] == {'min': 200, 'avg': 250, 'max': 300}
    assert {chapter['id'] for chapter in folder_b['chapters']} == {
        str(tree['chapterB'].id), str(tree['chapterC'].id), str(tree['chapterC1'].id),
    }


def test_chapter_stats_remain_chapter_only_not_subtree_aggregate(
    app, user, make_book, make_folder, make_chapter,
):
    tree = build_canonical_tree(user, make_book, make_folder, make_chapter)
    client = app.test_client()
    login(client, user)
    chapter_c = client.get(f"/api/chapters/{tree['chapterC'].id}/stats?days=0").json
    chapter_c1 = client.get(f"/api/chapters/{tree['chapterC1'].id}/stats?days=0").json
    assert (chapter_c['totalWords'], chapter_c1['totalWords']) == (300, 400)
    assert (chapter_c['activity']['mine']['wpm'], chapter_c1['activity']['mine']['wpm']) == (10.0, 10.0)


def test_workspace_recursive_stats_and_heatmap_use_exact_accessible_scope(
    app, cleanup, user, make_book, make_folder, make_chapter,
):
    tree = build_canonical_tree(user, make_book, make_folder, make_chapter)
    # Activity on a private book is deliberately outside this user's
    # workspace chapter scope. The heatmap/streak used to ignore that scope.
    other = User(username=f'outside-{uuid.uuid4().hex[:12]}', password_hash='x', is_admin=False)
    db.session.add(other)
    db.session.commit()
    cleanup['users'].append(other.id)
    private_book = make_book(name='Outside workspace', owner=other)
    private_chapter = make_chapter(folder=private_book, name='Outside chapter')
    db.session.add(ChapterWritingActivity(
        user_id=user.id,
        chapter_id=private_chapter.id,
        date=datetime.date.today(),
        hour_of_day=23,
        active_seconds=999,
        words_typed=999,
        words_pasted=999,
    ))
    db.session.commit()

    client = app.test_client()
    login(client, user)
    workspace = client.get('/api/stats?days=0').json
    assert workspace['totalWords'] == 1050
    assert (workspace['chapterCount'], workspace['completedChapterCount'], workspace['revisionCount']) == (5, 2, 15)
    assert (workspace['wordsTyped'], workspace['wordsPasted'], workspace['totalActiveSeconds']) == (105, 15, 630)
    assert workspace['avgWpm'] == 10.0
    assert sum(bucket['activeSeconds'] for bucket in workspace['heatmap']) == 630
    assert workspace['weekOverWeekWords']['thisWeek'] == 105
    assert workspace['busiestResource']['chapterId'] == str(tree['chapterC1'].id)


def test_activity_aggregate_helper_supports_resource_and_per_user_breakdowns(
    cleanup, user, make_book, make_folder, make_chapter,
):
    tree = build_canonical_tree(user, make_book, make_folder, make_chapter)
    collaborator = User(username=f'collab-{uuid.uuid4().hex[:12]}', password_hash='x', is_admin=False)
    db.session.add(collaborator)
    db.session.commit()
    cleanup['users'].append(collaborator.id)
    db.session.add(ChapterWritingActivity(
        user_id=collaborator.id,
        chapter_id=tree['chapterC'].id,
        date=datetime.date.today(),
        hour_of_day=20,
        active_seconds=42,
        words_typed=7,
        words_pasted=2,
    ))
    db.session.commit()

    scope = chapter_ids_under_folder(tree['folderB'].id)
    assert writing_activity_totals(scope) == {'wordsTyped': 97, 'wordsPasted': 14, 'activeSeconds': 582}
    assert writing_activity_totals(scope, user_id=user.id) == {
        'wordsTyped': 90, 'wordsPasted': 12, 'activeSeconds': 540,
    }
    assert writing_activity_totals(scope, user_id=collaborator.id) == {
        'wordsTyped': 7, 'wordsPasted': 2, 'activeSeconds': 42,
    }
