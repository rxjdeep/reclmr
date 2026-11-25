import pytest

from routes import loops


@pytest.fixture(autouse=True)
def _tmp_file(tmp_path, monkeypatch):
    monkeypatch.setattr(loops, '_FILE', tmp_path / 'loops.json')


def test_save_list_and_delete_a_loop(client, auth_headers):
    r = client.post('/api/music/loops', headers=auth_headers, json={'f': 'song1', 'name': 'solo', 'a': 91.5, 'b': 118})
    assert r.status_code == 200
    lst = r.get_json()['loops']
    assert lst[0]['name'] == 'solo' and lst[0]['a'] == 91.5 and lst[0]['b'] == 118
    assert client.get('/api/music/loops?f=song1', headers=auth_headers).get_json()['loops'] == lst
    assert client.get('/api/music/loops?f=other', headers=auth_headers).get_json()['loops'] == []
    r = client.delete('/api/music/loops', headers=auth_headers, json={'f': 'song1', 'id': lst[0]['id']})
    assert r.get_json()['loops'] == []


def test_a_loop_must_make_sense(client, auth_headers):
    for body in ({'f': 'x', 'a': 10, 'b': 5}, {'f': 'x', 'a': -1, 'b': 5}, {'f': 'x', 'a': 'no', 'b': 5}, {'a': 1, 'b': 2}):
        assert client.post('/api/music/loops', headers=auth_headers, json=body).status_code == 400


def test_an_unnamed_loop_gets_a_name_and_the_number_is_capped(client, auth_headers):
    r = client.post('/api/music/loops', headers=auth_headers, json={'f': 's', 'a': 1, 'b': 2})
    assert r.get_json()['loops'][0]['name'] == 'Loop 1'
    for i in range(loops._MAX_PER_SONG - 1):
        assert client.post('/api/music/loops', headers=auth_headers, json={'f': 's', 'a': 1, 'b': 2}).status_code == 200
    assert client.post('/api/music/loops', headers=auth_headers, json={'f': 's', 'a': 1, 'b': 2}).status_code == 400


def test_loops_need_a_login(client):
    assert client.get('/api/music/loops?f=s').status_code == 401
