"""Playlists without Navidrome: plain .m3u8 files (routes/playlists_local.py)."""
import pytest


@pytest.fixture
def lib(tmp_path, monkeypatch):
    """A small music folder with its own playlists folder, index and state, so nothing outside tmp_path is touched."""
    import shared
    import routes.music as music
    music_dir = tmp_path / 'music'
    (music_dir / 'Artist').mkdir(parents=True)
    for n in ('Artist - One.mp3', 'Artist - Two.mp3', 'Artist - Three.mp3'):
        (music_dir / 'Artist' / n).write_bytes(b'not really audio')
    monkeypatch.setattr(shared, 'MUSIC_DIR', music_dir)
    monkeypatch.setattr(music, '_INDEX_FILE', tmp_path / 'index.json')
    monkeypatch.setattr(music, '_STATE_FILE', tmp_path / 'state.json')
    monkeypatch.setenv('RECLMR_PLAYLISTS_DIR', str(tmp_path / 'playlists'))
    music._invalidate()
    yield {'dir': music_dir, 'pl': tmp_path / 'playlists', 'ids': ['Artist/Artist - One.mp3', 'Artist/Artist - Two.mp3', 'Artist/Artist - Three.mp3']}
    music._invalidate()


def _post(client, h, url, body):
    return client.post(url, json=body, headers=h)


def _make(client, h, lib, name='Road trip', ids=None):
    r = _post(client, h, '/api/music/playlists', {'name': name, 'ids': ids if ids is not None else lib['ids'][:2]})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()['id']


class TestLocalPlaylists:
    def test_create_writes_a_standard_m3u8_with_absolute_paths(self, client, auth_headers, lib):
        pid = _make(client, auth_headers, lib)
        text = (lib['pl'] / (pid + '.m3u8')).read_text()
        assert text.startswith('#EXTM3U\n#PLAYLIST:Road trip\n')
        assert str(lib['dir'] / 'Artist' / 'Artist - One.mp3') in text       # other players can open it as it is

    def test_library_lists_it_with_the_right_count(self, client, auth_headers, lib):
        pid = _make(client, auth_headers, lib)
        d = client.get('/api/music/library', headers=auth_headers).get_json()
        assert d['source'] == 'files'
        pl = next(p for p in d['playlists'] if p['id'] == pid)
        assert pl['name'] == 'Road trip' and pl['n'] == 2

    def test_same_name_gets_its_own_file(self, client, auth_headers, lib):
        a, b = _make(client, auth_headers, lib), _make(client, auth_headers, lib)
        assert a != b

    def test_add_skips_duplicates_and_honours_the_slot(self, client, auth_headers, lib):
        pid = _make(client, auth_headers, lib, ids=[lib['ids'][0]])
        url = '/api/music/playlist/%s/add' % pid
        assert _post(client, auth_headers, url, {'id': lib['ids'][1]}).get_json() == {'ok': True, 'dup': False, 'index': 1}
        assert _post(client, auth_headers, url, {'id': lib['ids'][1]}).get_json() == {'ok': True, 'dup': True}
        assert _post(client, auth_headers, url, {'id': lib['ids'][2], 'index': 0}).get_json()['index'] == 0
        assert client.get('/api/music/playlist/' + pid, headers=auth_headers).get_json()['ids'] == [lib['ids'][2], lib['ids'][0], lib['ids'][1]]

    def test_remove_rename_delete(self, client, auth_headers, lib):
        pid = _make(client, auth_headers, lib)
        r = _post(client, auth_headers, '/api/music/playlist/%s/remove' % pid, {'id': lib['ids'][0]}).get_json()
        assert r['removed'] == 1 and r['indices'] == [0]
        assert _post(client, auth_headers, '/api/music/playlist/%s/rename' % pid, {'name': 'Renamed'}).status_code == 200
        assert '#PLAYLIST:Renamed' in (lib['pl'] / (pid + '.m3u8')).read_text()
        assert _post(client, auth_headers, '/api/music/playlist/%s/delete' % pid, {}).status_code == 200
        assert not (lib['pl'] / (pid + '.m3u8')).exists()
        assert _post(client, auth_headers, '/api/music/playlist/%s/delete' % pid, {}).status_code == 404

    def test_order_saves_and_refuses_a_stale_page(self, client, auth_headers, lib):
        pid = _make(client, auth_headers, lib)
        url = '/api/music/playlist/%s/order' % pid
        rev = list(reversed(lib['ids'][:2]))
        assert _post(client, auth_headers, url, {'ids': rev, 'base': 2}).status_code == 200
        assert client.get('/api/music/playlist/' + pid, headers=auth_headers).get_json()['ids'] == rev
        assert _post(client, auth_headers, url, {'ids': rev, 'base': 5}).status_code == 409          # the page started from a different list
        assert _post(client, auth_headers, url, {'ids': rev + [lib['ids'][2]], 'base': 2}).status_code == 409   # would add a song

    def test_membership_and_inplaylists(self, client, auth_headers, lib):
        pid = _make(client, auth_headers, lib, ids=[lib['ids'][0]])
        assert client.get('/api/music/membership?id=' + lib['ids'][0], headers=auth_headers).get_json() == {'playlists': [pid]}
        assert client.get('/api/music/membership?id=' + lib['ids'][1], headers=auth_headers).get_json() == {'playlists': []}
        assert client.get('/api/music/inplaylists', headers=auth_headers).get_json() == {'ids': [lib['ids'][0]]}

    def test_a_playlist_file_from_another_player_shows_up(self, client, auth_headers, lib):
        lib['pl'].mkdir(exist_ok=True)
        (lib['pl'] / 'from-elsewhere.m3u8').write_text('#EXTM3U\n%s\nArtist/Artist - Two.mp3\n/somewhere/else.mp3\n' % (lib['dir'] / 'Artist' / 'Artist - One.mp3'))
        d = client.get('/api/music/library', headers=auth_headers).get_json()
        pl = next(p for p in d['playlists'] if p['id'] == 'from-elsewhere')
        assert pl['n'] == 2                                                   # an absolute and a relative line; the one outside the music folder is ignored
        assert client.get('/api/music/playlist/from-elsewhere', headers=auth_headers).get_json()['ids'] == lib['ids'][:2]

    def test_only_songs_in_the_music_folder_can_be_added(self, client, auth_headers, lib, tmp_path):
        (tmp_path / 'secret.mp3').write_bytes(b'x')
        pid = _make(client, auth_headers, lib, ids=[])
        for bad in ('../secret.mp3', '/etc/passwd', 'Artist/missing.mp3'):
            r = _post(client, auth_headers, '/api/music/playlist/%s/add' % pid, {'id': bad})
            assert r.status_code == 404, bad
        assert client.get('/api/music/playlist/' + pid, headers=auth_headers).get_json()['ids'] == []

    def test_a_playlist_id_cannot_name_another_file(self, client, auth_headers, lib):
        for pid in ('..%2F..%2Fetc%2Fpasswd', 'A_B', 'UPPER'):
            assert client.get('/api/music/playlist/' + pid, headers=auth_headers).status_code in (404, 400)
            assert _post(client, auth_headers, '/api/music/playlist/%s/delete' % pid, {}).status_code in (404, 400)


class TestFileModeExtras:
    def test_lrc_beside_a_song_gives_synced_lyrics(self, client, auth_headers, lib):
        song = lib['dir'] / 'Artist' / 'Artist - One.lrc'
        song.write_text('[ar:Artist]\n[ti:One]\n[00:01.50]first line\n[01:02.5][01:30.00]chorus\n', encoding='utf-8')
        d = client.get('/api/music/lyrics/Artist/Artist - One.mp3', headers=auth_headers).get_json()
        assert d['synced'] is True
        assert d['lines'][:2] == [[1500, 'first line'], [62500, 'chorus']] and d['lines'][2] == [90000, 'chorus']

    def test_opus_files_are_part_of_the_library(self, client, auth_headers, lib):
        (lib['dir'] / 'Artist' / 'Artist - Four.opus').write_bytes(b'x')
        import routes.music as music
        music._invalidate()
        d = client.get('/api/music/library', headers=auth_headers).get_json()
        assert any(t['f'].endswith('Four.opus') for t in d['tracks'])

    def test_quality_asks_for_a_converted_copy_and_says_what_it_sent(self, client, auth_headers, lib, monkeypatch):
        import routes.music as music
        made = lib['dir'] / 'made.mp3'
        made.write_bytes(b'ID3' + b'0' * 2000)
        monkeypatch.setattr(music, '_transcoded', lambda ident, rate: made if rate == 128 else None)
        r = client.get('/api/music/stream/Artist/Artist - One.mp3?q=128', headers=auth_headers)
        assert r.status_code == 200 and r.headers['X-Reclmr-Served'] == 'mp3-128'
        r = client.get('/api/music/stream/Artist/Artist - One.mp3?q=64', headers=auth_headers)          # could not be made: the file itself, honestly labelled
        assert r.headers['X-Reclmr-Served'] == 'original'

    def test_prewarm_is_accepted_without_navidrome(self, client, auth_headers, lib, monkeypatch):
        import routes.music as music
        monkeypatch.setattr(music, '_transcoded', lambda ident, rate: None)
        r = client.post('/api/music/prewarm', json={'id': 'Artist/Artist - One.mp3', 'q': 128}, headers=auth_headers)
        assert r.status_code == 202
