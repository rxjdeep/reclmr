import time

from routes import drive


def _reset():
    drive._S.update(ok=True, since=0.0, healing=False, last_offline=0.0, good=None, good_n=0, saved=0.0)


def lib(n):
    return {'source': 'navidrome', 'tracks': [{'f': str(i)} for i in range(n)], 'playlists': []}


def test_a_good_library_is_remembered_and_served_while_the_drive_is_away():
    _reset()
    assert drive.guard(lib(100))['tracks'][0]['f'] == '0' and drive._S['good_n'] == 100
    drive._S['ok'] = False
    drive._S['since'] = time.time()
    out = drive.guard(lib(3))
    assert len(out['tracks']) == 100 and out['offline'] and 'offline' in out['error'].lower()


def test_songs_marked_missing_right_after_an_outage_do_not_empty_the_library():
    _reset()
    drive.guard(lib(100))
    drive._S['last_offline'] = time.time() - 60                       # the drive was away a minute ago, now readable again, but the scan marked songs missing
    assert len(drive.guard(lib(40))['tracks']) == 100
    drive._S['last_offline'] = time.time() - 7200                     # two hours later a smaller library is just a smaller library
    assert len(drive.guard(lib(40))['tracks']) == 40


def test_a_library_is_left_alone_when_nothing_is_wrong():
    _reset()
    drive.guard(lib(100))
    assert len(drive.guard(lib(95))['tracks']) == 95


def test_probe_sees_missing_and_empty_folders(tmp_path):
    _reset()
    assert drive.probe(tmp_path / 'nope') is False
    (tmp_path / 'a.mp3').write_text('x')
    assert drive.probe(tmp_path) is True
    empty = tmp_path / 'e'
    empty.mkdir()
    assert drive.probe(empty) is True                                  # (no library yet: an empty folder is fine)
    drive._S['good_n'] = 50
    assert drive.probe(empty) is False                                 # (a library that has been seen: an empty folder means the drive is not mounted)
    _reset()


def test_drive_status_endpoint(client, auth_headers):
    _reset()
    r = client.get('/api/music/drive', headers=auth_headers)
    assert r.status_code == 200 and r.get_json()['ok'] is True
