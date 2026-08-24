import datetime

from flask import g

from extensions import db
from models import ChapterWritingActivity, Goal, GoalCadence, GoalPeriodHistory, GoalType
from services import (
    advance_goal_period,
    compute_writing_streak,
    local_date_bounds_utc,
    record_writing_activity,
    user_local_datetime,
    user_local_today,
)


UTC = datetime.timezone.utc


def utc(year, month, day, hour, minute=0):
    return datetime.datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_utc_date_crossing_buckets_activity_in_writers_local_day_and_hour(
    user, make_book, make_chapter,
):
    user.timezone = 'America/New_York'
    chapter = make_chapter(folder=make_book())
    instant = utc(2026, 8, 25, 2, 30)  # Aug 24, 10:30 PM EDT
    record_writing_activity(chapter, user.id, 60, 4, 1, occurred_at=instant)
    db.session.commit()

    row = ChapterWritingActivity.query.filter_by(chapter_id=chapter.id, user_id=user.id).one()
    assert row.date == datetime.date(2026, 8, 24)
    assert row.hour_of_day == 22
    assert user_local_today(user, instant) == datetime.date(2026, 8, 24)


def test_local_midnight_creates_distinct_days_and_two_day_streak(
    user, make_book, make_chapter,
):
    user.timezone = 'America/New_York'
    chapter = make_chapter(folder=make_book())
    record_writing_activity(chapter, user.id, 60, 1, 0, occurred_at=utc(2026, 8, 25, 3, 59))
    record_writing_activity(chapter, user.id, 60, 1, 0, occurred_at=utc(2026, 8, 25, 4, 1))
    db.session.commit()

    rows = ChapterWritingActivity.query.filter_by(chapter_id=chapter.id, user_id=user.id).order_by(
        ChapterWritingActivity.date
    ).all()
    assert [(row.date, row.hour_of_day) for row in rows] == [
        (datetime.date(2026, 8, 24), 23),
        (datetime.date(2026, 8, 25), 0),
    ]
    assert compute_writing_streak(user.id, today=datetime.date(2026, 8, 25)) == {'current': 2, 'longest': 2}


def test_spring_dst_transition_skips_nonexistent_local_hour_without_losing_activity(
    user, make_book, make_chapter,
):
    user.timezone = 'America/New_York'
    chapter = make_chapter(folder=make_book())
    # 01:30 EST jumps to 03:30 EDT; there is no local 02:xx hour.
    record_writing_activity(chapter, user.id, 60, 2, 0, occurred_at=utc(2026, 3, 8, 6, 30))
    record_writing_activity(chapter, user.id, 60, 3, 0, occurred_at=utc(2026, 3, 8, 7, 30))
    db.session.commit()

    rows = ChapterWritingActivity.query.filter_by(chapter_id=chapter.id, user_id=user.id).order_by(
        ChapterWritingActivity.hour_of_day
    ).all()
    assert [(row.date, row.hour_of_day, row.words_typed) for row in rows] == [
        (datetime.date(2026, 3, 8), 1, 2),
        (datetime.date(2026, 3, 8), 3, 3),
    ]


def test_fall_dst_repeated_hour_accumulates_once_in_same_local_bucket(
    user, make_book, make_chapter,
):
    user.timezone = 'America/New_York'
    chapter = make_chapter(folder=make_book())
    # Both instants are local 01:30, first EDT and then EST. They are two real
    # intervals and should atomically accumulate in one aggregate bucket.
    record_writing_activity(chapter, user.id, 60, 2, 0, occurred_at=utc(2026, 11, 1, 5, 30))
    record_writing_activity(chapter, user.id, 60, 3, 0, occurred_at=utc(2026, 11, 1, 6, 30))
    db.session.commit()

    rows = ChapterWritingActivity.query.filter_by(chapter_id=chapter.id, user_id=user.id).all()
    assert len(rows) == 1
    assert (rows[0].date, rows[0].hour_of_day, rows[0].words_typed, rows[0].active_seconds) == (
        datetime.date(2026, 11, 1), 1, 5, 120,
    )


def test_daily_goal_and_history_do_not_roll_at_utc_midnight_before_local_midnight(
    user, make_book, make_chapter,
):
    user.timezone = 'America/New_York'
    book = make_book()
    chapter = make_chapter(folder=book)
    goal = Goal(
        user_id=user.id,
        folder_id=book.id,
        name='Local day',
        goal_type=GoalType.words,
        target=5,
        cadence=GoalCadence.daily,
        start_date=datetime.date(2026, 8, 24),
        period_start=datetime.date(2026, 8, 24),
    )
    db.session.add(goal)
    record_writing_activity(chapter, user.id, 60, 5, 0, occurred_at=utc(2026, 8, 25, 2, 30))
    db.session.commit()

    # UTC says Aug 25, but New York still says Aug 24: no rollover yet.
    local_before_midnight = user_local_today(user, utc(2026, 8, 25, 2, 30))
    advance_goal_period(goal, today=local_before_midnight)
    assert goal.period_start == datetime.date(2026, 8, 24)
    assert GoalPeriodHistory.query.filter_by(goal_id=goal.id).count() == 0

    advance_goal_period(goal, today=user_local_today(user, utc(2026, 8, 25, 4, 30)))
    db.session.commit()
    history = GoalPeriodHistory.query.filter_by(goal_id=goal.id).one()
    assert goal.period_start == datetime.date(2026, 8, 25)
    assert (history.period_start, history.period_end, history.current, history.achieved) == (
        datetime.date(2026, 8, 24), datetime.date(2026, 8, 24), 5, True,
    )


def test_local_midnight_utc_bounds_follow_dst_offsets(user):
    user.timezone = 'America/New_York'
    spring_start, spring_end = local_date_bounds_utc(
        datetime.date(2026, 3, 8), datetime.date(2026, 3, 8), user
    )
    fall_start, fall_end = local_date_bounds_utc(
        datetime.date(2026, 11, 1), datetime.date(2026, 11, 1), user
    )
    assert spring_end - spring_start == datetime.timedelta(hours=23)
    assert fall_end - fall_start == datetime.timedelta(hours=25)


def test_timezone_api_validates_iana_and_browser_default_never_overwrites_override(app, user):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    g.pop('csrf_token', None)
    csrf = client.get('/api/auth/me').json['csrfToken']
    headers = {'X-CSRFToken': csrf}
    created_at = user.created_at

    detected = client.patch(
        '/api/me/timezone', json={'timezone': 'America/New_York', 'onlyIfUnset': True}, headers=headers
    )
    assert detected.status_code == 200
    assert detected.json['timezone'] == 'America/New_York'
    not_overwritten = client.patch(
        '/api/me/timezone', json={'timezone': 'America/Chicago', 'onlyIfUnset': True}, headers=headers
    )
    assert not_overwritten.json['timezone'] == 'America/New_York'
    explicit = client.patch('/api/me/timezone', json={'timezone': 'America/Los_Angeles'}, headers=headers)
    assert explicit.json['timezone'] == 'America/Los_Angeles'
    invalid = client.patch('/api/me/timezone', json={'timezone': 'UTC-04:00'}, headers=headers)
    assert invalid.status_code == 400
    db.session.refresh(user)
    assert user.created_at == created_at


def test_timezone_change_does_not_rewrite_historical_aggregate_rows(
    user, make_book, make_chapter,
):
    user.timezone = 'America/New_York'
    chapter = make_chapter(folder=make_book())
    instant = utc(2026, 8, 25, 2, 30)
    record_writing_activity(chapter, user.id, 60, 1, 0, occurred_at=instant)
    db.session.commit()
    original = ChapterWritingActivity.query.filter_by(chapter_id=chapter.id, user_id=user.id).one()
    original_bucket = (original.date, original.hour_of_day)

    user.timezone = 'America/Los_Angeles'
    db.session.commit()
    unchanged = db.session.get(ChapterWritingActivity, original.id)
    assert (unchanged.date, unchanged.hour_of_day) == original_bucket
    assert user_local_datetime(user, instant).date() == datetime.date(2026, 8, 24)
    assert user_local_datetime(user, instant).hour == 19
