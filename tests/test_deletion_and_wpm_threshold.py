"""P0.11: deletion-aware writing statistics and the minimum-sample WPM
threshold. See services.calculate_wpm / services.words_written_from and
api.api_heartbeat_chapter_presence's deletedWordsTotal handling."""
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

from flask import g

from extensions import db
from models import ChapterPresence, ChapterWritingActivity, User, ResourceShare, ShareRole
from services import MIN_WPM_ACTIVE_SECONDS, MIN_WPM_TYPED_WORDS, calculate_wpm, words_written_from


def authenticated_client(app, user):
    client = app.test_client()
    with client.session_transaction() as session:
        session.clear()
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    g.pop('_login_user', None)
    g.pop('csrf_token', None)
    csrf_token = client.get('/api/auth/me').json['csrfToken']
    return client, {'X-CSRFToken': csrf_token}


def heartbeat(client, headers, chapter_id, **overrides):
    payload = {
        'wordCount': 0,
        'typedWordsTotal': 0,
        'pastedWordsTotal': 0,
        'deletedWordsTotal': 0,
        'hadTypingInput': False,
        **overrides,
    }
    return client.post(f'/api/chapters/{chapter_id}/presence', json=payload, headers=headers)


def age_presence(chapter_id, user_id, seconds=20):
    row = ChapterPresence.query.filter_by(chapter_id=chapter_id, user_id=user_id).one()
    row.last_seen = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds)
    db.session.commit()


def activity_row(chapter_id, user_id):
    typed, pasted, deleted, active = db.session.query(
        db.func.coalesce(db.func.sum(ChapterWritingActivity.words_typed), 0),
        db.func.coalesce(db.func.sum(ChapterWritingActivity.words_pasted), 0),
        db.func.coalesce(db.func.sum(ChapterWritingActivity.words_deleted), 0),
        db.func.coalesce(db.func.sum(ChapterWritingActivity.active_seconds), 0),
    ).filter(
        ChapterWritingActivity.chapter_id == chapter_id,
        ChapterWritingActivity.user_id == user_id,
    ).one()
    return int(typed), int(pasted), int(deleted), int(active)


# ---------------------------------------------------------------- deletion --

def test_heartbeat_credits_deletion_delta(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    age_presence(chapter.id, user.id)

    response = heartbeat(
        client, headers, chapter.id,
        wordCount=450, typedWordsTotal=500, deletedWordsTotal=50, hadTypingInput=True,
    )
    assert response.status_code == 200
    typed, pasted, deleted, active = activity_row(chapter.id, user.id)
    assert (typed, pasted, deleted) == (500, 0, 50)
    assert active > 0

    presence = ChapterPresence.query.filter_by(chapter_id=chapter.id, user_id=user.id).one()
    assert presence.last_deleted_words == 50


def test_duplicated_heartbeat_does_not_double_count_deletion(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    payload = {'wordCount': 40, 'typedWordsTotal': 60, 'deletedWordsTotal': 20, 'hadTypingInput': True}
    assert heartbeat(client, headers, chapter.id, **payload).status_code == 200
    assert heartbeat(client, headers, chapter.id, **payload).status_code == 200
    _, _, deleted, _ = activity_row(chapter.id, user.id)
    assert deleted == 20


def test_dropped_then_caught_up_heartbeat_credits_deletion_exactly_once(app, user, make_book, make_chapter):
    """A heartbeat can be dropped in transit -- the next one's larger
    cumulative deletedWordsTotal must catch the server up to the true total,
    not lose the gap or double it."""
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    # First heartbeat (deletedWordsTotal=10) is "dropped" -- never sent.
    # The next one jumps straight to the cumulative total of 30.
    assert heartbeat(
        client, headers, chapter.id,
        wordCount=70, typedWordsTotal=100, deletedWordsTotal=30, hadTypingInput=True,
    ).status_code == 200
    _, _, deleted, _ = activity_row(chapter.id, user.id)
    assert deleted == 30


def test_reload_reset_deletion_counter_clamps_without_phantom_or_lost_credit(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    assert heartbeat(client, headers, chapter.id, deletedWordsTotal=15).status_code == 200
    # Page reload: client's cumulative counters restart at 0, diffing
    # negative against the 15 already recorded -- clamped, no phantom
    # credit, and the baseline still advances to 0 so the next real delta
    # is measured from there.
    assert heartbeat(client, headers, chapter.id, deletedWordsTotal=0).status_code == 200
    assert heartbeat(client, headers, chapter.id, deletedWordsTotal=4).status_code == 200
    _, _, deleted, _ = activity_row(chapter.id, user.id)
    assert deleted == 15 + 4


def test_concurrent_heartbeats_do_not_double_count_deletion(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    age_presence(chapter.id, user.id)

    payload = {'wordCount': 80, 'typedWordsTotal': 100, 'deletedWordsTotal': 20, 'hadTypingInput': True}
    # Captured as a plain value, not the ORM object -- chapter's attributes
    # are expired after age_presence's commit above, and re-reading chapter.id
    # from inside a worker thread (which has no Flask app context of its own
    # until heartbeat()'s own client.post() pushes one) would try to lazily
    # refetch it outside any app context and blow up before the request even
    # starts.
    chapter_id = chapter.id
    clients = [authenticated_client(app, user) for _ in range(2)]
    barrier = threading.Barrier(2)

    def send(index):
        c, h = clients[index]
        barrier.wait(timeout=5)
        return heartbeat(c, h, chapter_id, **payload).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(send, range(2)))
    assert statuses == [200, 200]
    _, _, deleted, _ = activity_row(chapter.id, user.id)
    assert deleted == 20


def test_existing_activity_rows_default_words_deleted_to_zero(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    row = ChapterWritingActivity(
        user_id=user.id, chapter_id=chapter.id, date=datetime.date.today(), hour_of_day=9,
        active_seconds=120, words_typed=200, words_pasted=10,
    )
    db.session.add(row)
    db.session.commit()
    db.session.refresh(row)
    assert row.words_deleted == 0


def test_words_written_is_net_of_typed_and_deleted(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    age_presence(chapter.id, user.id)
    assert heartbeat(
        client, headers, chapter.id,
        wordCount=350, typedWordsTotal=500, deletedWordsTotal=150, hadTypingInput=True,
    ).status_code == 200

    stats = client.get(f'/api/chapters/{chapter.id}/stats?days=0').json
    totals = stats['activity']['totals']
    assert (totals['wordsTyped'], totals['wordsDeleted'], totals['wordsWritten']) == (500, 150, 350)
    mine = stats['activity']['mine']
    assert (mine['wordsTyped'], mine['wordsDeleted'], mine['wordsWritten']) == (500, 150, 350)


def test_words_written_floors_at_zero_when_deleted_exceeds_typed():
    # Deleting more than was ever typed this session (e.g. deleting a large
    # pasted block via genuine keyboard delete) must never go negative.
    assert words_written_from(10, 40) == 0
    assert words_written_from(40, 10) == 30


def test_contributor_stats_expose_deleted_and_written_independently(
    app, cleanup, user, make_book, make_chapter,
):
    collaborator = User(username='collab-del-test', password_hash='x', is_admin=False)
    db.session.add(collaborator)
    db.session.commit()
    cleanup['users'].append(collaborator.id)

    book = make_book(name='Deletion Contributors')
    chapter = make_chapter(folder=book, name='Shared')
    db.session.add(ChapterWritingActivity(
        user_id=user.id, chapter_id=chapter.id, date=datetime.date.today(), hour_of_day=8,
        active_seconds=600, words_typed=300, words_pasted=0, words_deleted=100,
    ))
    db.session.add(ChapterWritingActivity(
        user_id=collaborator.id, chapter_id=chapter.id, date=datetime.date.today(), hour_of_day=9,
        active_seconds=600, words_typed=50, words_pasted=0, words_deleted=10,
    ))
    db.session.add(ResourceShare(chapter_id=chapter.id, user_id=collaborator.id, role=ShareRole.viewer))
    db.session.commit()

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    stats = client.get(f'/api/chapters/{chapter.id}/stats?days=0').json
    rows = {row['userId']: row for row in stats['activity']['contributors']}
    assert (rows[str(user.id)]['wordsTyped'], rows[str(user.id)]['wordsDeleted'], rows[str(user.id)]['wordsWritten']) == (
        300, 100, 200,
    )
    assert (
        rows[str(collaborator.id)]['wordsTyped'],
        rows[str(collaborator.id)]['wordsDeleted'],
        rows[str(collaborator.id)]['wordsWritten'],
    ) == (50, 10, 40)


# ------------------------------------------------------------- WPM threshold --

def test_wpm_below_both_thresholds_calculation_helper():
    assert calculate_wpm(24, 120) is None


def test_wpm_below_word_threshold_only():
    assert calculate_wpm(MIN_WPM_TYPED_WORDS - 1, 59) is None


def test_wpm_at_exact_thresholds_is_valid():
    assert calculate_wpm(MIN_WPM_TYPED_WORDS, MIN_WPM_ACTIVE_SECONDS) == round(
        MIN_WPM_TYPED_WORDS / (MIN_WPM_ACTIVE_SECONDS / 60), 1
    )


def test_wpm_below_time_threshold_only():
    assert calculate_wpm(MIN_WPM_TYPED_WORDS, MIN_WPM_ACTIVE_SECONDS - 1) is None


def test_wpm_threshold_via_heartbeat_endpoint(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    age_presence(chapter.id, user.id, seconds=MIN_WPM_ACTIVE_SECONDS - 1)
    # 24 words, MIN_WPM_ACTIVE_SECONDS-1 seconds -- below both thresholds.
    below = heartbeat(
        client, headers, chapter.id,
        wordCount=24, typedWordsTotal=MIN_WPM_TYPED_WORDS - 1, hadTypingInput=True,
    )
    assert below.json['averageWpm'] is None

    age_presence(chapter.id, user.id, seconds=MIN_WPM_ACTIVE_SECONDS)
    at_threshold = heartbeat(
        client, headers, chapter.id,
        wordCount=25, typedWordsTotal=MIN_WPM_TYPED_WORDS, hadTypingInput=True,
    )
    assert at_threshold.json['averageWpm'] is not None


def test_pasted_words_cannot_satisfy_wpm_threshold(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    age_presence(chapter.id, user.id, seconds=120)
    # 100 pasted words, 0 typed, but hadTypingInput True so active time still
    # accrues -- WPM must stay null because pasted words never count toward
    # the typed-word threshold.
    response = heartbeat(
        client, headers, chapter.id,
        wordCount=100, pastedWordsTotal=100, typedWordsTotal=0, hadTypingInput=True,
    )
    assert response.json['averageWpm'] is None
    typed, pasted, _, _ = activity_row(chapter.id, user.id)
    assert (typed, pasted) == (0, 100)


def test_deleted_words_do_not_reduce_wpm_numerator(app, user, make_book, make_chapter):
    chapter = make_chapter(folder=make_book())
    client, headers = authenticated_client(app, user)
    assert heartbeat(client, headers, chapter.id).status_code == 200
    age_presence(chapter.id, user.id, seconds=120)
    response = heartbeat(
        client, headers, chapter.id,
        wordCount=20, typedWordsTotal=100, deletedWordsTotal=80, hadTypingInput=True,
    )
    # Gross typed (100) over ~120s of active time comfortably clears both
    # thresholds -- WPM uses that gross figure, unaffected by the 80 deleted.
    assert response.json['averageWpm'] == calculate_wpm(100, response_active_seconds(chapter, user))


def response_active_seconds(chapter, user):
    _, _, _, active = activity_row(chapter.id, user.id)
    return active


def test_collaborator_wpm_is_independent_and_no_blended_resource_wpm(
    app, cleanup, user, make_book, make_chapter,
):
    collaborator = User(username='collab-wpm-test', password_hash='x', is_admin=False)
    db.session.add(collaborator)
    db.session.commit()
    cleanup['users'].append(collaborator.id)

    book = make_book(name='Independent WPM')
    chapter = make_chapter(folder=book, name='Shared')
    # user: comfortably above threshold. collaborator: below threshold.
    db.session.add(ChapterWritingActivity(
        user_id=user.id, chapter_id=chapter.id, date=datetime.date.today(), hour_of_day=8,
        active_seconds=120, words_typed=60, words_pasted=0,
    ))
    db.session.add(ChapterWritingActivity(
        user_id=collaborator.id, chapter_id=chapter.id, date=datetime.date.today(), hour_of_day=9,
        active_seconds=120, words_typed=10, words_pasted=0,
    ))
    db.session.add(ResourceShare(chapter_id=chapter.id, user_id=collaborator.id, role=ShareRole.viewer))
    db.session.commit()

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    stats = client.get(f'/api/chapters/{chapter.id}/stats?days=0').json
    assert 'wpm' not in stats['activity']['totals']
    rows = {row['userId']: row for row in stats['activity']['contributors']}
    assert rows[str(user.id)]['wpm'] == 30.0
    assert rows[str(collaborator.id)]['wpm'] is None
