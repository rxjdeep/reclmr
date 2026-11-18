"""Asking the library in plain words: tags from MusicBrainz, a filter from the model, matching, and the no-model fallback."""
import pytest

from routes import ask

TRACKS = [
    {'f': 'a1', 't': 'Same Beef', 'ar': 'Bohemia', 'as': [['A1', 'Bohemia']], 'al': 'Album', 'y': '2018', 'g': '', 'pc': 3, 'fav': True, 'n': 1},
    {'f': 'a2', 't': 'Brown Munde', 'ar': 'AP Dhillon', 'as': [['A2', 'AP Dhillon']], 'al': 'Hidden Gems', 'y': '2020', 'g': '', 'pc': 0, 'n': 2},
    {'f': 'a3', 't': 'Get Busy', 'ar': 'Yeat', 'as': [['A3', 'Yeat']], 'al': '2093', 'y': '2022', 'g': 'Rap', 'pc': 5, 'n': 3},
    {'f': 'a4', 't': 'ਦਿਲ', 'ar': 'Somebody', 'as': [['A4', 'Somebody']], 'al': 'x', 'y': '', 'g': '', 'pc': 0, 'n': 4},
    {'f': 'a5', 't': 'Wavy Trap', 'ar': 'Other Punjabi Rapper', 'as': [['A5', 'Other Punjabi Rapper']], 'al': 'y', 'y': '2021', 'g': '', 'pc': 0, 'n': 5},
]
TAGS = {'A1': {'tags': ['punjabi', 'hip hop', 'india']}, 'A2': {'tags': ['punjabi', 'bhangra', 'india']}, 'A3': {'tags': ['trap', 'hip hop']},
        'A5': {'tags': ['punjabi', 'trap']}}


@pytest.fixture(autouse=True)
def _data(monkeypatch, tmp_path):
    monkeypatch.setattr(ask, '_TAGS_FILE', tmp_path / 'ai_tags.json')       # never the real file
    monkeypatch.setattr(ask, '_tracks', lambda: TRACKS)
    monkeypatch.setattr(ask, '_start_enrich', lambda: False)                # never the network
    ask._save(TAGS)


def _ids(f):
    return [t['f'] for t in ask._apply(ask._clean(f, ask._vocab(TRACKS, TAGS)), TRACKS, TAGS)]


def test_title_script_is_a_language_tag():
    assert 'punjabi' in ask._track_tags(TRACKS[3], TAGS)


def test_vocab_counts_artists_and_keeps_common_tags():
    v = ask._vocab(TRACKS, TAGS)
    assert 'punjabi' in v and 'hip hop' in v and 'bhangra' not in v            # bhangra has one artist only


def test_clean_only_keeps_real_tags():
    f = ask._clean({'any_tags': ['punjabi', 'martian']}, ask._vocab(TRACKS, TAGS))
    assert f['any_tags'] == ['punjabi']


def test_punjabi_songs_with_the_plain_matcher():
    f = ask._plain_filter('show me all the punjabi songs ive got', ask._vocab(TRACKS, TAGS))
    assert f['any_tags'] == ['punjabi'] and f['words'] == []
    assert _ids(f) == ['a2', 'a1', 'a4', 'a5'] or set(_ids(f)) == {'a1', 'a2', 'a4', 'a5'}


def test_exclude_and_flags():
    base = {'any_tags': ['punjabi'], 'not_tags': ['trap'], 'artists': [], 'words': [], 'year_from': None, 'year_to': None, 'liked': False, 'unplayed': False, 'sort': ''}
    assert set(_ids(base)) == {'a1', 'a2', 'a4'}
    assert _ids(dict(base, liked=True)) == ['a1']
    assert set(_ids(dict(base, unplayed=True))) == {'a2', 'a4'}
    assert _ids(dict(base, year_from=2019, year_to=2020)) == ['a2']


def test_endpoint_uses_the_model_filter(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ask, '_ollama_filter', lambda q, v: {'any_tags': ['punjabi'], 'not_tags': ['trap'], 'artists': [], 'words': [], 'year_from': None,
                                                              'year_to': None, 'liked': False, 'unplayed': False, 'sort': ''})
    r = client.get('/api/music/ask?q=punjabi but not trap', headers=auth_headers).get_json()
    assert r['how'] == 'model' and set(r['ids']) == {'a1', 'a2', 'a4'} and 'punjabi' in r['understood']


def test_endpoint_falls_back_without_a_model(client, auth_headers, monkeypatch):
    def down(q, v):
        raise RuntimeError('no ollama')
    monkeypatch.setattr(ask, '_ollama_filter', down)
    r = client.get('/api/music/ask?q=punjabi songs but not trap', headers=auth_headers).get_json()
    assert r['how'] == 'words' and set(r['ids']) == {'a1', 'a2', 'a4'}


def test_plain_questions_never_wake_the_model(client, auth_headers, monkeypatch):
    def boom(q, v):
        raise AssertionError('the model must not run for a plain question')
    monkeypatch.setattr(ask, '_ollama_filter', boom)
    r = client.get('/api/music/ask?q=show me all the punjabi songs ive got', headers=auth_headers).get_json()
    assert r['how'] == 'tags' and r['n'] == 4 and r['ms'] < 1000
    r = client.get('/api/music/ask?q=punjabi trap', headers=auth_headers).get_json()
    assert r['ids'] == ['a5']                                                      # two tags: both must fit


def test_endpoint_needs_login(client):
    assert client.get('/api/music/ask?q=punjabi').status_code == 401


def test_endpoint_needs_a_question(client, auth_headers):
    assert client.get('/api/music/ask?q=', headers=auth_headers).status_code == 400


def test_model_flags_need_the_sentence_to_back_them_up():
    base = {'any_tags': [], 'not_tags': [], 'artists': [], 'words': ['test'], 'year_from': None, 'year_to': None, 'liked': True, 'unplayed': True, 'sort': 'popular'}
    v = ask._vocab(TRACKS, TAGS)
    f = ask._clean(base, v, 'show me all the test songs ive got')
    assert not f['liked'] and not f['unplayed'] and f['sort'] == ''
    f = ask._clean(base, v, 'my liked songs i never played')
    assert f['liked'] and f['unplayed']


def test_a_name_that_is_also_a_tag_is_an_artist(client, auth_headers, monkeypatch):
    monkeypatch.setattr(ask, '_ollama_filter', lambda q, v: (_ for _ in ()).throw(AssertionError('no model')))
    TRACKS.append({'f': 'a6', 't': 'Around the World', 'ar': 'Punk Trap', 'as': [['A6', 'Punk Trap']], 'al': 'z', 'y': '', 'g': '', 'pc': 0, 'n': 6})
    try:
        r = client.get('/api/music/ask?q=punk trap', headers=auth_headers).get_json()
        assert r['ids'] == ['a6'] and 'by punk trap' in r['understood']
    finally:
        TRACKS.pop()


def test_release_languages_become_artist_tags(monkeypatch):
    class R:
        status_code = 200

        def json(self):
            rel = [{'text-representation': {'language': 'pan'}}] * 20 + [{'text-representation': {'language': 'hin'}}] + [{'text-representation': {'language': 'mul'}}] * 4
            return {'releases': rel}
    monkeypatch.setattr(ask.requests, 'get', lambda *a, **k: R())
    assert ask._release_langs('x') == ['punjabi']                  # 20 of 21 releases; one Hindi release is too few; "multiple" is no language


def test_languages_pass_and_a_language_is_in_the_vocab_even_for_one_artist(monkeypatch):
    monkeypatch.setattr(ask, '_release_langs', lambda m: ['punjabi'])
    monkeypatch.setattr(ask, '_MB_GAP', 0)
    tags = {'A9': {'tags': ['india'], 'mb': '0' * 36, 'n': 'X'}}
    ask._lang_pass(tags)
    assert tags['A9']['lang'] == ['punjabi'] and 'punjabi' in tags['A9']['tags'] and tags['A9']['rl'] == 1
    ask._lang_pass(tags)                                            # not asked twice
    t = [{'f': 'z', 't': 'q', 'ar': 'X', 'as': [['A9', 'X']], 'al': '', 'y': '', 'g': ''}]
    assert 'punjabi' in ask._vocab(t, tags)
