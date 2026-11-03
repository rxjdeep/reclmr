"""Security response headers, books position API, Ollama caps, OS detection."""
import os
import time

import pytest


class TestSecurityHeaders:
    def test_headers_on_html(self, client):
        r = client.get('/')
        h = r.headers
        assert h.get('X-Content-Type-Options') == 'nosniff'
        assert h.get('X-Frame-Options') == 'DENY'
        assert h.get('Referrer-Policy') == 'no-referrer'
        assert 'default-src' in h.get('Content-Security-Policy', '')
        assert 'frame-ancestors' in h.get('Content-Security-Policy', '')

    def test_api_responses_not_cached(self, client, login):
        r = client.get('/api/auth/check')
        assert r.headers.get('Cache-Control') == 'no-store'


class TestOsDetection:
    def test_detect_os_shape(self):
        from shared import detect_os
        info = detect_os()
        assert info['name'] and info['system']
        assert info['system'] in ('Linux', 'Darwin', 'Windows', '')

    def test_no_hardcoded_os_string(self):
        import routes.system as system_module
        src = open(system_module.__file__).read()
        assert 'Linux Mint' not in src


class TestOllamaCaps:
    def test_missing_messages_rejected(self, client, auth_headers):
        r = client.post('/api/ollama/chat', json={}, headers=auth_headers)
        assert r.status_code == 400

    def test_message_flood_rejected(self, client, auth_headers):
        msgs = [{'role': 'user', 'content': 'x'}] * 41
        r = client.post('/api/ollama/chat', json={'messages': msgs}, headers=auth_headers)
        assert r.status_code == 400

    def test_huge_payload_rejected(self, client, auth_headers):
        msgs = [{'role': 'user', 'content': 'x' * 200_000}]
        r = client.post('/api/ollama/chat', json={'messages': msgs}, headers=auth_headers)
        assert r.status_code == 400

    def test_out_of_range_params_rejected(self, client, auth_headers):
        r = client.post('/api/ollama/chat', json={
            'messages': [{'role': 'user', 'content': 'hi'}],
            'temperature': 99,
        }, headers=auth_headers)
        assert r.status_code == 400

    def test_requires_auth(self, client):
        r = client.post('/api/ollama/chat', json={'messages': [{'role': 'user', 'content': 'hi'}]})
        assert r.status_code == 401


class TestBookPosition:
    @pytest.fixture
    def book_id(self, tmp_path, monkeypatch):
        import routes.books as books_module
        monkeypatch.setattr(books_module, 'AUDIO_DIR', tmp_path)
        return 'Unit_Test_Book'

    def test_roundtrip(self, client, auth_headers, book_id):
        r = client.post(f'/api/book/{book_id}/position',
                        json={'audio': {'chapter': 4, 'time': 123}, 'mode': 'audio'},
                        headers=auth_headers)
        assert r.status_code == 200
        r2 = client.get(f'/api/book/{book_id}/position', headers=auth_headers)
        data = r2.get_json()
        assert data['audio']['chapter'] == 4
        assert data['audio']['time'] == 123
        assert data['mode'] == 'audio'

    def test_string_chapter_rejected(self, client, auth_headers, book_id):
        client.post(f'/api/book/{book_id}/position',
                    json={'audio': {'chapter': '../../etc', 'time': 999}},
                    headers=auth_headers)
        data = client.get(f'/api/book/{book_id}/position', headers=auth_headers).get_json()
        assert 'chapter' not in data.get('audio', {})

    def test_newest_write_wins(self, client, auth_headers, book_id):
        client.post(f'/api/book/{book_id}/position',
                    json={'audio': {'chapter': 1, 'time': 10}}, headers=auth_headers)
        data = client.get(f'/api/book/{book_id}/position', headers=auth_headers).get_json()
        first_updated = data['updated']
        assert data['audio']['chapter'] == 1
        time.sleep(0.05)
        client.post(f'/api/book/{book_id}/position',
                    json={'audio': {'chapter': 7, 'time': 50}}, headers=auth_headers)
        data = client.get(f'/api/book/{book_id}/position', headers=auth_headers).get_json()
        assert data['audio']['chapter'] == 7
        assert data['updated'] >= first_updated

    def test_position_requires_auth(self, client, book_id):
        assert client.get(f'/api/book/{book_id}/position').status_code == 401
        r = client.post(f'/api/book/{book_id}/position', json={'audio': {'chapter': 1}})
        assert r.status_code == 401


class TestBookCounts:
    def test_list_counts_correct(self, client, auth_headers, tmp_path, monkeypatch):
        import json as _json
        import routes.books as books_module
        import shared
        books_dir = tmp_path / 'books'
        books_dir.mkdir()
        chapters = [{'title': f'C{i}', 'text': 'w ' * 50} for i in range(12)]
        (books_dir / 'Twelve.json').write_text(_json.dumps(chapters))
        monkeypatch.setattr(shared, 'BOOKS_DIR', books_dir)
        monkeypatch.setattr(books_module, 'AUDIO_DIR', tmp_path / 'audio')
        (tmp_path / 'audio').mkdir()
        r = client.get('/api/books', headers=auth_headers)
        assert r.status_code == 200
        book = [b for b in r.get_json() if b['id'] == 'Twelve'][0]
        assert book['total_chapters'] == 12
        assert book['chapters_done'] == 0


class TestTelemetryUsage:
    @pytest.fixture(autouse=True)
    def _own_usage_file(self, tmp_path, monkeypatch):      # never write the real usage log from a test
        import routes.telemetry as t
        monkeypatch.setattr(t, 'USAGE_FILE', tmp_path / 'usage.json')

    def _post(self, client, login, body):
        h = {'Authorization': 'Bearer ' + login['session']}
        return client.post('/api/telemetry/app-usage', json=body, headers=h)

    def test_junk_is_clamped_not_stored(self, client, login):
        r = self._post(client, login, {'app_id': 'x' * 500, 'action': '<script>', 'duration': 'NaN?'})
        e = r.get_json()['entry']
        assert r.status_code == 200
        assert len(e['app_id']) == 64 and e['action'] == 'open' and e['duration'] == 0

    def test_huge_duration_is_capped(self, client, login):
        e = self._post(client, login, {'app_id': 'a', 'action': 'close', 'duration': 10 ** 12}).get_json()['entry']
        assert e['duration'] == 86400

    def test_log_does_not_grow_forever(self, client, login, monkeypatch):
        import json, routes.telemetry as t
        monkeypatch.setattr(t, 'USAGE_MAX', 5)
        for i in range(9):
            self._post(client, login, {'app_id': 'a%d' % i, 'action': 'open'})
        assert len(json.loads(t.USAGE_FILE.read_text())) == 5
