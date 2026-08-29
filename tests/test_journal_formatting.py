"""P1.1A: Journal date/time formatting preferences. See
services.format_journal_date / format_journal_time / journal_write_today
and api.api_update_settings."""
import datetime
import uuid

from flask import g

from extensions import db
from models import Chapter, Folder, ResourceShare, ShareRole, User
from services import (
    DEFAULT_JOURNAL_DATE_FORMAT,
    DEFAULT_JOURNAL_TIME_FORMAT,
    JOURNAL_DATE_FORMATS,
    JOURNAL_TIME_FORMATS,
    format_journal_date,
    format_journal_time,
    journal_write_today,
)


def authenticated_client(app, user):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    g.pop('csrf_token', None)
    csrf_token = client.get('/api/auth/me').json['csrfToken']
    return client, {'X-CSRFToken': csrf_token}


def make_collaborator(cleanup, name='collab', timezone=None):
    u = User(username=f'{name}-{uuid.uuid4().hex[:12]}', password_hash='x', is_admin=False, timezone=timezone)
    db.session.add(u)
    db.session.commit()
    cleanup['users'].append(u.id)
    return u


def write_today(client, headers, book_id):
    return client.post(f'/api/books/{book_id}/journal/today', headers=headers)


# --------------------------------------------------------------------- defaults --

def test_new_user_defaults_to_long_month_day_year_and_12_hour(app, user):
    assert user.journal_date_format == 'long_month_day_year'
    assert user.journal_time_format == '12_hour'


def test_migration_backfilled_defaults_are_valid(app, user):
    # Every user row (old or freshly created) must satisfy the same check
    # constraints the migration installed.
    assert user.journal_date_format in JOURNAL_DATE_FORMATS
    assert user.journal_time_format in JOURNAL_TIME_FORMATS


# ------------------------------------------------------------------- validation --

def test_each_valid_date_format_id_accepted(app, user):
    client, headers = authenticated_client(app, user)
    for fmt in JOURNAL_DATE_FORMATS:
        resp = client.patch('/api/me/settings', json={'journalDateFormat': fmt}, headers=headers)
        assert resp.status_code == 200
        assert resp.json['journalDateFormat'] == fmt


def test_invalid_date_format_id_rejected(app, user):
    client, headers = authenticated_client(app, user)
    resp = client.patch('/api/me/settings', json={'journalDateFormat': 'yyyy_mm_dd_slashes'}, headers=headers)
    assert resp.status_code == 400
    db.session.refresh(user)
    assert user.journal_date_format == DEFAULT_JOURNAL_DATE_FORMAT


def test_each_valid_time_format_id_accepted(app, user):
    client, headers = authenticated_client(app, user)
    for fmt in JOURNAL_TIME_FORMATS:
        resp = client.patch('/api/me/settings', json={'journalTimeFormat': fmt}, headers=headers)
        assert resp.status_code == 200
        assert resp.json['journalTimeFormat'] == fmt


def test_invalid_time_format_id_rejected(app, user):
    client, headers = authenticated_client(app, user)
    resp = client.patch('/api/me/settings', json={'journalTimeFormat': '36_hour'}, headers=headers)
    assert resp.status_code == 400
    db.session.refresh(user)
    assert user.journal_time_format == DEFAULT_JOURNAL_TIME_FORMAT


# --------------------------------------------------------------- date formatting --

def test_all_eight_exact_date_outputs():
    d = datetime.date(2026, 8, 29)
    assert format_journal_date(d, 'long_month_day_year') == 'August 29, 2026'
    assert format_journal_date(d, 'short_month_day_year') == 'Aug 29, 2026'
    assert format_journal_date(d, 'day_long_month_year') == '29 August 2026'
    assert format_journal_date(d, 'day_short_month_year') == '29 Aug 2026'
    assert format_journal_date(d, 'us_numeric') == '08/29/2026'
    assert format_journal_date(d, 'day_first_numeric') == '29/08/2026'
    assert format_journal_date(d, 'iso') == '2026-08-29'
    assert format_journal_date(d, 'weekday_long') == 'Saturday, August 29, 2026'


def test_date_formats_zero_pad_numeric_month_and_day():
    d = datetime.date(2026, 1, 5)
    assert format_journal_date(d, 'us_numeric') == '01/05/2026'
    assert format_journal_date(d, 'day_first_numeric') == '05/01/2026'


# --------------------------------------------------------------- time formatting --

def test_time_formatting_am_pm_midnight_noon_and_24_hour():
    tz = 'America/New_York'
    # 10:42 AM EDT = 14:42 UTC
    am = datetime.datetime(2026, 8, 29, 14, 42, tzinfo=datetime.timezone.utc)
    assert format_journal_time(am, tz, '12_hour') == '10:42 AM'
    assert format_journal_time(am, tz, '24_hour') == '10:42'
    # 10:42 PM EDT = 02:42 UTC (next day)
    pm = datetime.datetime(2026, 8, 30, 2, 42, tzinfo=datetime.timezone.utc)
    assert format_journal_time(pm, tz, '12_hour') == '10:42 PM'
    assert format_journal_time(pm, tz, '24_hour') == '22:42'
    # Midnight EDT = 04:00 UTC
    midnight = datetime.datetime(2026, 8, 29, 4, 0, tzinfo=datetime.timezone.utc)
    assert format_journal_time(midnight, tz, '12_hour') == '12:00 AM'
    assert format_journal_time(midnight, tz, '24_hour') == '00:00'
    # Noon EDT = 16:00 UTC
    noon = datetime.datetime(2026, 8, 29, 16, 0, tzinfo=datetime.timezone.utc)
    assert format_journal_time(noon, tz, '12_hour') == '12:00 PM'
    assert format_journal_time(noon, tz, '24_hour') == '12:00'


def test_time_formatting_never_includes_seconds():
    instant = datetime.datetime(2026, 8, 29, 14, 42, 37, tzinfo=datetime.timezone.utc)
    assert ':' not in format_journal_time(instant, 'UTC', '12_hour').split(' ')[0][3:]
    label = format_journal_time(instant, 'UTC', '24_hour')
    assert label.count(':') == 1


def test_time_formatting_is_dst_and_timezone_aware():
    # Same UTC instant, two different zones -> different local labels.
    instant = datetime.datetime(2026, 8, 29, 18, 0, tzinfo=datetime.timezone.utc)
    ny = format_journal_time(instant, 'America/New_York', '24_hour')
    la = format_journal_time(instant, 'America/Los_Angeles', '24_hour')
    assert ny == '14:00'
    assert la == '11:00'


# --------------------------------------------------------- new journal chapter --

def test_new_journal_chapter_uses_owner_date_preference(app, user, make_book):
    for fmt, expected in [
        ('iso', '2026-08-29'),
        ('day_first_numeric', '29/08/2026'),
        ('weekday_long', 'Saturday, August 29, 2026'),
    ]:
        user.journal_date_format = fmt
        db.session.commit()
        book = make_book(name=f'Format Test {fmt} {uuid.uuid4().hex[:6]}')
        book.book_type = 'journal'
        db.session.commit()

        import services
        original = services.user_local_today
        services.user_local_today = lambda u=None, at_utc=None: datetime.date(2026, 8, 29)
        try:
            chapter, created = journal_write_today(book)
            db.session.commit()
        finally:
            services.user_local_today = original
        assert created is True
        assert chapter.name == expected


# ------------------------------------------------------ existing chapter safety --

def test_changing_format_does_not_rename_todays_existing_chapter(app, user, make_book):
    user.journal_date_format = 'long_month_day_year'
    db.session.commit()
    book = make_book(name='Preservation Book')
    book.book_type = 'journal'
    db.session.commit()
    chapter, created = journal_write_today(book)
    db.session.commit()
    assert created is True
    original_name = chapter.name
    original_id = chapter.id

    user.journal_date_format = 'iso'
    db.session.commit()

    chapter2, created2 = journal_write_today(book)
    db.session.commit()
    assert created2 is False
    assert chapter2.id == original_id
    assert chapter2.name == original_name  # never renamed to the new format


def test_next_day_uses_newly_changed_format(app, user, make_book):
    user.journal_date_format = 'long_month_day_year'
    db.session.commit()
    book = make_book(name='Next Day Format Book')
    book.book_type = 'journal'
    db.session.commit()

    import services
    original = services.user_local_today
    services.user_local_today = lambda u=None, at_utc=None: datetime.date(2026, 8, 29)
    try:
        today_chapter, _ = journal_write_today(book)
        db.session.commit()
    finally:
        services.user_local_today = original
    assert today_chapter.name == 'August 29, 2026'

    user.journal_date_format = 'iso'
    db.session.commit()

    services.user_local_today = lambda u=None, at_utc=None: datetime.date(2026, 8, 30)
    try:
        tomorrow_chapter, created = journal_write_today(book)
        db.session.commit()
    finally:
        services.user_local_today = original
    assert created is True
    assert tomorrow_chapter.id != today_chapter.id
    assert tomorrow_chapter.name == '2026-08-30'
    # Yesterday's Chapter (still under the old format) remains untouched.
    db.session.refresh(today_chapter)
    assert today_chapter.name == 'August 29, 2026'


# ----------------------------------------------------------------- time change --

def test_time_format_change_affects_next_response_not_existing_content(app, user, make_book):
    user.journal_time_format = '12_hour'
    db.session.commit()
    book = make_book(name='Time Change Book')
    book.book_type = 'journal'
    db.session.commit()
    client, headers = authenticated_client(app, user)

    first = write_today(client, headers, book.id).json
    assert 'AM' in first['entryTimeLabel'] or 'PM' in first['entryTimeLabel']

    user.journal_time_format = '24_hour'
    db.session.commit()

    second = write_today(client, headers, book.id).json
    assert 'AM' not in second['entryTimeLabel'] and 'PM' not in second['entryTimeLabel']
    assert first['chapter']['id'] == second['chapter']['id']


# --------------------------------------------------------------------- sharing --

def test_shared_editor_preferences_do_not_override_owner(app, cleanup, user, make_book):
    user.journal_date_format = 'iso'
    user.journal_time_format = '24_hour'
    user.timezone = 'America/New_York'
    db.session.commit()

    editor = make_collaborator(cleanup, name='editor-own-prefs', timezone='America/Los_Angeles')
    editor.journal_date_format = 'weekday_long'
    editor.journal_time_format = '12_hour'
    db.session.commit()

    book = make_book(name='Shared Formatting Book', owner=user)
    book.book_type = 'journal'
    db.session.add(ResourceShare(folder_id=book.id, user_id=editor.id, role=ShareRole.editor))
    db.session.commit()

    client, headers = authenticated_client(app, editor)
    resp = write_today(client, headers, book.id)
    assert resp.status_code == 200
    data = resp.json
    assert data['journalTimezone'] == 'America/New_York'
    assert 'AM' not in data['entryTimeLabel'] and 'PM' not in data['entryTimeLabel']
    chapter = db.session.get(Chapter, uuid.UUID(data['chapter']['id']))
    assert chapter.name == chapter.journal_date.isoformat()  # owner's 'iso' preference, not the editor's


# ------------------------------------------------------------- book type round-trip --

def test_book_type_round_trip_preserves_current_owner_formatting_for_future_entries(app, user, make_book):
    user.journal_date_format = 'short_month_day_year'
    db.session.commit()
    book = make_book(name='Round Trip Format Book')
    book.book_type = 'journal'
    db.session.commit()

    import services
    original = services.user_local_today
    services.user_local_today = lambda u=None, at_utc=None: datetime.date(2026, 8, 29)
    try:
        chapter, _ = journal_write_today(book)
        db.session.commit()
    finally:
        services.user_local_today = original
    assert chapter.name == 'Aug 29, 2026'

    book.book_type = 'novel'
    db.session.commit()
    book.book_type = 'journal'
    db.session.commit()

    services.user_local_today = lambda u=None, at_utc=None: datetime.date(2026, 8, 30)
    try:
        chapter2, created2 = journal_write_today(book)
        db.session.commit()
    finally:
        services.user_local_today = original
    assert created2 is True
    assert chapter2.name == 'Aug 30, 2026'
