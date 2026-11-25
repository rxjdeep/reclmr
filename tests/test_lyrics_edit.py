import pytest

from routes import music


@pytest.fixture(autouse=True)
def _tmp_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(music, '_EDIT_DIR', tmp_path / 'edits')


def test_edited_lyrics_win_and_come_back_timed(client, auth_headers):
    text = '[ti:x]\n[00:01.50] first line\n[00:03.00] second line <00:03.2>word\n'
    r = client.post('/api/music/lyrics/song-1', headers=auth_headers, json={'text': text})
    assert r.status_code == 200 and r.get_json()['synced'] is True
    d = client.get('/api/music/lyrics/song-1', headers=auth_headers).get_json()
    assert d['edited'] is True and d['synced'] is True
    assert d['lines'][0] == [1500, 'first line'] and d['lines'][1][0] == 3000 and d['lines'][1][1].startswith('second line')


def test_plain_and_empty_edits(client, auth_headers):
    d = client.post('/api/music/lyrics/song-2', headers=auth_headers, json={'text': 'one\ntwo'}).get_json()
    assert d['synced'] is False and [l[1] for l in d['lines']] == ['one', 'two']
    d = client.post('/api/music/lyrics/song-3', headers=auth_headers, json={'text': ''}).get_json()        # "this song has no lyrics"
    assert d['lines'] == [] and client.get('/api/music/lyrics/song-3', headers=auth_headers).get_json()['lines'] == []


def test_reset_removes_the_edit_and_bad_requests_are_refused(client, auth_headers):
    client.post('/api/music/lyrics/song-4', headers=auth_headers, json={'text': '[00:01.00] x'})
    assert client.delete('/api/music/lyrics/song-4', headers=auth_headers).status_code == 200
    assert music._edited_lyrics('song-4') is None
    assert client.delete('/api/music/lyrics/never-edited', headers=auth_headers).status_code == 200
    assert client.post('/api/music/lyrics/song-5', headers=auth_headers, json={'text': 5}).status_code == 400
    assert client.post('/api/music/lyrics/song-5', headers=auth_headers, json={'text': 'x' * 300000}).status_code == 400
