import pytest

import shared
from routes import drive, music


@pytest.fixture
def music_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, 'MUSIC_DIR', tmp_path)
    monkeypatch.setattr(music, '_nd_conf', lambda: False)
    monkeypatch.setattr(music, '_APP_DIR', tmp_path / 'app')
    (tmp_path / 'app').mkdir()
    monkeypatch.setitem(drive._S, 'ok', True)
    music._deleted.clear()
    return tmp_path


def test_a_song_and_its_lyrics_file_are_deleted(client, auth_headers, music_dir):
    (music_dir / 'a.mp3').write_bytes(b'x')
    (music_dir / 'a.lrc').write_text('[00:01.00] hi')
    (music_dir / 'b.mp3').write_bytes(b'x')
    r = client.delete('/api/music/file/a.mp3', headers=auth_headers)
    assert r.status_code == 200
    assert not (music_dir / 'a.mp3').exists() and not (music_dir / 'a.lrc').exists()
    assert (music_dir / 'b.mp3').exists()                                       # nothing else is touched
    assert client.delete('/api/music/file/a.mp3', headers=auth_headers).status_code == 404


def test_only_music_inside_the_music_folder_can_be_deleted(client, auth_headers, music_dir, tmp_path_factory):
    (music_dir / 'notes.txt').write_text('keep')
    assert client.delete('/api/music/file/notes.txt', headers=auth_headers).status_code == 404
    outside = tmp_path_factory.mktemp('outside') / 'x.mp3'
    outside.write_bytes(b'x')
    assert client.delete('/api/music/file/../../%s' % outside, headers=auth_headers).status_code in (404, 308)
    assert outside.exists() and (music_dir / 'notes.txt').exists()
    sub = music_dir / 'sub'
    sub.mkdir()
    assert client.delete('/api/music/file/sub', headers=auth_headers).status_code == 404       # not a folder either
    assert sub.exists()


def test_nothing_is_deleted_while_the_drive_is_offline(client, auth_headers, music_dir, monkeypatch):
    (music_dir / 'a.mp3').write_bytes(b'x')
    monkeypatch.setitem(drive._S, 'ok', False)
    assert client.delete('/api/music/file/a.mp3', headers=auth_headers).status_code == 503
    assert (music_dir / 'a.mp3').exists()


def test_a_deleted_song_is_hidden_until_the_scan_has_caught_up():
    music._deleted.clear()
    music._deleted['x'] = __import__('time').time()
    out = music._hide_deleted({'tracks': [{'f': 'x'}, {'f': 'y'}]})
    assert [t['f'] for t in out['tracks']] == ['y']
    music._deleted['x'] = 0                                                        # long ago: Navidrome has caught up
    assert len(music._hide_deleted({'tracks': [{'f': 'x'}]})['tracks']) == 1
    music._deleted.clear()


def test_delete_needs_a_login(client):
    assert client.delete('/api/music/file/a.mp3').status_code == 401
