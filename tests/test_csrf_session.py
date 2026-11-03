import time
from itsdangerous import URLSafeTimedSerializer
from flask_wtf.csrf import generate_csrf
from extensions import db
from models import Chapter, Folder


def test_csrf_token_does_not_expire_after_one_hour(app, user, make_book, make_chapter):
    """Verify that CSRF tokens remain valid beyond the default 3600s time limit."""
    book = make_book('Test Book', owner=user)
    folder = Folder(parent_id=book.id, book_id=book.id, name='Test Folder')
    db.session.add(folder)
    db.session.commit()
    chapter = make_chapter(folder=folder, name='Test Chapter')

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['csrf_token'] = 'test-csrf-secret'

    s = URLSafeTimedSerializer(app.secret_key, salt='wtf-csrf-token')

    # Simulate token minted 5 hours ago (18,000 seconds)
    real_time = time.time
    time.time = lambda: real_time() - 18000
    try:
        old_token = s.dumps('test-csrf-secret')
    finally:
        time.time = real_time

    # Mutating request with the 5-hour-old token should succeed
    res = client.patch(
        f'/api/chapters/{chapter.id}',
        headers={'X-CSRFToken': old_token},
        json={'contentHtml': '<p>updated text</p>'},
    )
    assert res.status_code == 200, res.data.decode()
    data = res.get_json()
    assert data['contentHtml'] == '<p>updated text</p>'


def test_csrf_error_returns_structured_json(app, user):
    """Verify that invalid CSRF tokens return structured JSON error with code 'csrf_error'."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['csrf_token'] = 'test-csrf-secret'

    res = client.patch(
        f'/api/chapters/{user.id}',  # Any mutating endpoint
        headers={'X-CSRFToken': 'completely-invalid-token'},
        json={},
    )
    assert res.status_code == 400
    assert res.is_json
    data = res.get_json()
    assert data.get('code') == 'csrf_error'
    assert 'error' in data
