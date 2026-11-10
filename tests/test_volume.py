"""Laptop volume relay: the phone queues a step, the agent's next poll picks it up and reports the new level."""
import threading
import time

from routes import volume


def _reset():
    with volume._cv:
        volume._agents.clear()


def test_needs_login(client):
    assert client.get('/api/volume/agents').status_code == 401
    assert client.post('/api/volume/step', json={'step': 5}).status_code == 401


def test_no_agent_is_a_clear_error(client, auth_headers):
    _reset()
    r = client.post('/api/volume/step', json={'step': 5}, headers=auth_headers)
    assert r.status_code == 409 and r.get_json()['error'] == 'no laptop connected'


def test_bad_step_rejected(client, auth_headers):
    _reset()
    for bad in (0, 'x', None):
        assert client.post('/api/volume/step', json={'step': bad}, headers=auth_headers).status_code in (400, 409)


def test_step_reaches_agent_and_level_comes_back(client, auth_headers, monkeypatch):
    _reset()
    monkeypatch.setattr(volume, '_WAIT', 3)
    got = {}

    def agent():
        with client.application.test_client() as c:
            r = c.post('/api/volume/agent/poll', json={'name': 'lap', 'level': 40, 'platform': 'Linux', 'backend': 'wpctl'}, headers=auth_headers)
            got['cmds'] = r.get_json()['cmds']
            c.post('/api/volume/agent/poll', json={'name': 'lap', 'level': 45}, headers=auth_headers)   # reports after applying

    t = threading.Thread(target=agent); t.start()
    time.sleep(0.5)
    r = client.post('/api/volume/step', json={'step': 5}, headers=auth_headers)
    t.join()
    assert got['cmds'] == [{'a': 'step', 'v': 5}]
    assert r.get_json() == {'ok': True, 'agent': 'lap', 'level': 45, 'muted': False}
    ag = client.get('/api/volume/agents', headers=auth_headers).get_json()['agents']
    assert ag[0]['name'] == 'lap' and ag[0]['online'] and ag[0]['level'] == 45


def test_step_is_clamped(client, auth_headers, monkeypatch):
    _reset()
    monkeypatch.setattr(volume, '_WAIT', 2)
    got = {}
    t = threading.Thread(target=lambda: got.update(r=client.application.test_client().post('/api/volume/agent/poll', json={'name': 'lap', 'level': 10}, headers=auth_headers).get_json()))
    t.start(); time.sleep(0.4)
    client.post('/api/volume/step', json={'step': 999}, headers=auth_headers)
    t.join()
    assert got['r']['cmds'] == [{'a': 'step', 'v': 25}]
