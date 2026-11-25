import pytest

import tagtools
from routes import health, music


def T(i, title, artist, album='A', sx='m4a', d=200, **kw):
    return {'f': str(i), 't': title, 'ar': artist, 'aa': artist, 'al': album, 'sx': sx, 'd': d, 'as': [[str(i), artist]], **kw}


@pytest.fixture
def fake_library(monkeypatch):
    lib = [T(1, 'Rich Boy', 'Galantis/Zack Martino'), T(2, 'Fine', 'Mac Miller'), T(3, 'Loose', 'Someone', album=''),
           T(4, 'Same Song', 'Dup Artist', d=200), T(5, 'Same Song', 'Dup Artist', d=201, album='B'), T(6, 'Same Song (live)', 'Dup Artist', d=330, album='L'),
           T(7, 'Solo', 'Flac Artist', sx='flac', li='p1', al='Swimming'), T(8, 'Hurt', 'Flac Artist', sx='m4a', li='p2', al='Swimming')]
    monkeypatch.setattr(music, '_library_data', lambda: {'tracks': lib})
    monkeypatch.setattr(music, '_nd_conf', lambda: False)
    monkeypatch.setattr(health, '_local', lambda t: 'x')
    monkeypatch.setattr(tagtools, 'release_dates', lambda p: ('2018-08-03', '2018-08-03'))
    monkeypatch.setattr(tagtools, 'apply_release_date', lambda p, target, dry=True: True)
    return lib


def test_scan_finds_each_kind_of_problem(fake_library):
    g = {x['kind']: x for x in health.scan()['groups']}
    assert g['unsplit']['count'] == 1 and g['unsplit']['items'][0]['to'] == 'Galantis; Zack Martino'
    assert g['split']['count'] == 1 and g['split']['items'][0]['t'] == 'Swimming' and g['split']['fixable']
    assert g['noalbum']['count'] == 1
    assert g['dups']['count'] == 1 and g['dups']['items'][0]['n'] == 2            # the live take (different title and length) does not count
    assert not g['noalbum']['fixable'] and g['unsplit']['fixable']


def test_endpoints(client, auth_headers, fake_library):
    r = client.get('/api/music/health', headers=auth_headers)
    assert r.status_code == 200 and r.get_json()['songs'] == 8
    assert client.post('/api/music/health/fix/nonsense', headers=auth_headers).status_code == 400


def test_health_needs_a_login(client):
    assert client.get('/api/music/health').status_code == 401
    assert client.post('/api/music/health/fix/unsplit').status_code == 401
