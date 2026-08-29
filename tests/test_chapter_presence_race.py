import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

from flask import g

from extensions import db
from models import ChapterPresence, ChapterWritingActivity


def authenticated_client(app, user):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    # conftest keeps one outer app context for each test, so Flask-WTF's
    # request-local cache otherwise leaks across these separately cookie'd
    # test clients and only the first client receives a session secret.
    g.pop('csrf_token', None)
    csrf_token = client.get('/api/auth/me').json['csrfToken']
    return client, {'X-CSRFToken': csrf_token}


def heartbeat(client, headers, chapter_id, **overrides):
    payload = {
        'wordCount': 0,
        'typedWordsTotal': 0,
        'pastedWordsTotal': 0,
        'hadTypingInput': False,
        **overrides,
    }
    return client.post(f'/api/chapters/{chapter_id}/presence', json=payload, headers=headers)


def concurrent_heartbeats(app, user, chapter_id, payloads):
    clients = [authenticated_client(app, user) for _ in payloads]
    barrier = threading.Barrier(len(payloads))

    def send(index):
        client, headers = clients[index]
        barrier.wait(timeout=5)
        response = heartbeat(client, headers, chapter_id, **payloads[index])
        return response.status_code, response.get_data(as_text=True)

    with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
        return list(pool.map(send, range(len(payloads))))


def activity_totals(chapter_id, user_id):
    typed, pasted, active = db.session.query(
        db.func.coalesce(db.func.sum(ChapterWritingActivity.words_typed), 0),
        db.func.coalesce(db.func.sum(ChapterWritingActivity.words_pasted), 0),
        db.func.coalesce(db.func.sum(ChapterWritingActivity.active_seconds), 0),
    ).filter(
        ChapterWritingActivity.chapter_id == chapter_id,
        ChapterWritingActivity.user_id == user_id,
    ).one()
    return int(typed), int(pasted), int(active)


def age_presence(chapter_id, user_id, seconds=20):
    row = ChapterPresence.query.filter_by(chapter_id=chapter_id, user_id=user_id).one()
    row.last_seen = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds)
    db.session.commit()


def test_concurrent_first_heartbeat_creates_exactly_one_presence_row(
    app, user, make_book, make_chapter,
):
    chapter = make_chapter(folder=make_book())
    responses = concurrent_heartbeats(app, user, chapter.id, [{}, {}])
    assert [status for status, _ in responses] == [200, 200]
    assert ChapterPresence.query.filter_by(chapter_id=chapter.id, user_id=user.id).count() == 1


def test_concurrent_cumulative_activity_is_not_double_counted(
    app, user, make_book, make_chapter,
):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    age_presence(chapter.id, user.id)

    payload = {
        'wordCount': 13,
        'typedWordsTotal': 10,
        'pastedWordsTotal': 3,
        'hadTypingInput': True,
    }
    responses = concurrent_heartbeats(app, user, chapter.id, [payload, payload])
    assert [status for status, _ in responses] == [200, 200]
    typed, pasted, active = activity_totals(chapter.id, user.id)
    assert (typed, pasted) == (10, 3)
    assert 19 <= active <= 21


def test_duplicate_heartbeat_adds_zero_typed_or_pasted_words(
    app, user, make_book, make_chapter,
):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    payload = {
        'wordCount': 7,
        'typedWordsTotal': 5,
        'pastedWordsTotal': 2,
        'hadTypingInput': True,
    }
    assert heartbeat(client, headers, chapter.id, **payload).status_code == 200
    assert heartbeat(client, headers, chapter.id, **payload).status_code == 200
    assert activity_totals(chapter.id, user.id)[:2] == (5, 2)


def test_paste_only_duplicate_never_adds_typing_time_or_duplicate_paste_credit(
    app, user, make_book, make_chapter,
):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    age_presence(chapter.id, user.id)
    payload = {'wordCount': 8, 'pastedWordsTotal': 8, 'hadTypingInput': False}
    assert heartbeat(client, headers, chapter.id, **payload).status_code == 200
    assert heartbeat(client, headers, chapter.id, **payload).status_code == 200
    assert activity_totals(chapter.id, user.id) == (0, 8, 0)


def test_normal_sequential_heartbeat_preserves_p0_2_accounting(
    app, user, make_book, make_chapter,
):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    age_presence(chapter.id, user.id)
    response = heartbeat(
        client,
        headers,
        chapter.id,
        wordCount=12,
        typedWordsTotal=10,
        pastedWordsTotal=2,
        hadTypingInput=True,
    )
    assert response.status_code == 200
    # Only 10 typed words -- below MIN_WPM_TYPED_WORDS (25, see P0.11's
    # minimum-sample threshold), so no WPM yet even though this interval's
    # accounting itself is credited correctly (asserted below).
    assert response.json['averageWpm'] is None
    presence = ChapterPresence.query.filter_by(chapter_id=chapter.id, user_id=user.id).one()
    assert (presence.last_word_count, presence.last_typed_words, presence.last_pasted_words) == (12, 10, 2)
    typed, pasted, active = activity_totals(chapter.id, user.id)
    assert (typed, pasted) == (10, 2)
    assert 19 <= active <= 21


def test_reload_counter_reset_rebaselines_without_phantom_or_lost_credit(
    app, user, make_book, make_chapter,
):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    assert heartbeat(client, headers, chapter.id, wordCount=10, typedWordsTotal=10).status_code == 200
    # Reload: cumulative-since-mount counters restart at zero. The negative
    # delta is clamped, while the presence baseline still advances to zero.
    assert heartbeat(client, headers, chapter.id, wordCount=10, typedWordsTotal=0).status_code == 200
    assert heartbeat(client, headers, chapter.id, wordCount=13, typedWordsTotal=3).status_code == 200
    assert activity_totals(chapter.id, user.id)[:2] == (13, 0)
