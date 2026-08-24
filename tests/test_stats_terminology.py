from flask import g


def authenticated_client(app, user):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    g.pop('csrf_token', None)
    csrf_token = client.get('/api/auth/me').json['csrfToken']
    return client, {'X-CSRFToken': csrf_token}


def test_editor_stats_settings_are_user_wide_and_word_count_gates_wpm(app, user):
    client, headers = authenticated_client(app, user)

    settings = client.get('/api/me/settings').json
    assert settings['showWordCount'] is True
    assert settings['showAverageWpm'] is True

    hidden = client.patch('/api/me/settings', json={'showWordCount': False}, headers=headers)
    assert hidden.status_code == 200
    assert hidden.json['showWordCount'] is False
    assert hidden.json['showAverageWpm'] is False

    words_only = client.patch('/api/me/settings', json={'showWordCount': True}, headers=headers)
    assert words_only.status_code == 200
    assert words_only.json['showWordCount'] is True
    assert words_only.json['showAverageWpm'] is False

    both = client.patch('/api/me/settings', json={'showAverageWpm': True}, headers=headers)
    assert both.status_code == 200
    assert both.json['showAverageWpm'] is True

    invalid = client.patch('/api/me/settings', json={'showAverageWpm': 'yes'}, headers=headers)
    assert invalid.status_code == 400


def test_insufficient_wpm_data_is_null_on_every_stats_surface(
    app, user, make_book, make_chapter,
):
    book = make_book(name='No WPM Data')
    chapter = make_chapter(folder=book, name='Empty Chapter')
    client, headers = authenticated_client(app, user)

    workspace = client.get('/api/stats?days=0').json
    book_stats = client.get(f'/api/folders/{book.id}/stats?days=0').json
    chapter_stats = client.get(f'/api/chapters/{chapter.id}/stats?days=0').json
    heartbeat = client.post(
        f'/api/chapters/{chapter.id}/presence',
        json={
            'wordCount': 0,
            'typedWordsTotal': 0,
            'pastedWordsTotal': 0,
            'hadTypingInput': False,
        },
        headers=headers,
    )

    assert workspace['avgWpm'] is None
    assert book_stats['activity']['mine']['wpm'] is None
    assert chapter_stats['activity']['mine']['wpm'] is None
    assert heartbeat.status_code == 200
    assert heartbeat.json == {'averageWpm': None}
