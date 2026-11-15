"""Ask the music library in plain words: "show me all the punjabi songs i've got".

Two parts, so the answer is quick and does not depend on a model's memory of obscure artists:

1. Tags. Every artist in the library gets tags (genres, a country) from MusicBrainz, once, in the background (about one request per second, no key).
   A song is also tagged by the script of its title (Gurmukhi, Devanagari, Kana, ...) and by its own genre tag. Tags are kept in ai_tags.json.
2. A small local model (Ollama) turns the question into a filter. It is shown the tags that really exist in this library and picks from them, so it
   only has to understand the sentence, never to know who an artist is. With no model running a plain word match answers instead.
"""
import json
import os
import re
import threading
import time
from pathlib import Path

import requests
from flask import Blueprint, jsonify, request

import shared
from shared import limiter

bp = Blueprint('ask', __name__)

_APP_DIR = Path(__file__).resolve().parent.parent
_TAGS_FILE = _APP_DIR / 'ai_tags.json'
_MODEL = os.environ.get('RECLMR_ASK_MODEL', 'qwen2.5:3b-instruct')
_MB_URL = 'https://musicbrainz.org/ws/2/artist'
_MB_UA = 'reclmr-library-tagger/1.0 (self-hosted music app)'
_MB_GAP = 1.1                                    # seconds between MusicBrainz requests (they allow one a second)
_lock = threading.Lock()
_cache = {}                                       # question -> filter, so asking again is instant
_job = {'running': False, 'done': 0, 'total': 0, 'started': 0.0}

# the script a title is written in tells its language when the artist's tags do not
_SCRIPTS = [
    (r'[਀-੿]', 'punjabi'), (r'[ऀ-ॿ]', 'hindi'), (r'[぀-ヿ]', 'japanese'), (r'[가-힯]', 'korean'),
    (r'[一-鿿]', 'chinese'), (r'[؀-ۿ]', 'arabic'), (r'[Ѐ-ӿ]', 'russian'), (r'[฀-๿]', 'thai'),
    (r'[஀-௿]', 'tamil'), (r'[ఀ-౿]', 'telugu'), (r'[ঀ-৿]', 'bengali'),
]


def _load():
    try:
        return json.loads(_TAGS_FILE.read_text())
    except Exception:
        return {}


def _save(d):
    tmp = _TAGS_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False))
    tmp.replace(_TAGS_FILE)


def _norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s&+-]', ' ', str(s or '').lower())).strip()


def _tracks():
    from routes import music
    return music._library_data().get('tracks', [])


def _artist_ids(t):
    ids = [c[0] for c in (t.get('as') or []) if isinstance(c, (list, tuple)) and c]
    return ids or ([t['ai']] if t.get('ai') else [])


def _script_tags(t):
    s = '%s %s' % (t.get('t', ''), t.get('al', ''))
    return [name for rx, name in _SCRIPTS if re.search(rx, s)]


def _track_tags(t, tags):
    """Everything a song can be found by: its artists' tags, its own genre and the script of its title."""
    out = set(_script_tags(t))
    if t.get('g'):
        out.add(_norm(t['g']))
    for aid in _artist_ids(t):
        out.update(tags.get(aid, {}).get('tags', []))
    return out


def _vocab(tracks, tags, limit=140):
    """The tags this library really has, most common first (counted per artist, so one big artist does not swamp it)."""
    seen = {}
    for t in tracks:
        for tg in _track_tags(t, tags):
            seen.setdefault(tg, set()).update(_artist_ids(t) or [t['f']])
    ranked = sorted(seen.items(), key=lambda kv: -len(kv[1]))
    return [k for k, v in ranked if len(v) >= 2][:limit]


# ─── 1. tagging artists from MusicBrainz ───────────────────────────────────────────────────────

def _mb_lookup(name):
    r = requests.get(_MB_URL, params={'query': 'artist:"%s"' % name.replace('"', ' '), 'fmt': 'json', 'limit': 3},
                     headers={'User-Agent': _MB_UA}, timeout=15)
    if r.status_code == 503:
        time.sleep(5)
        return None
    r.raise_for_status()
    want = _norm(name)
    for a in r.json().get('artists', []):
        if int(a.get('score', 0)) >= 90 and _norm(a.get('name')) == want:
            tg = [_norm(x['name']) for x in sorted(a.get('tags', []), key=lambda x: -x.get('count', 0))[:8] if x.get('name')]
            area = (a.get('area') or {}).get('name') or ''
            if area:
                tg.append(_norm(area))
            if a.get('country') == 'IN' and 'india' not in tg:
                tg.append('india')
            return {'tags': [x for x in dict.fromkeys(tg) if x], 'country': a.get('country') or '', 'mb': a.get('id', '')}
    return {'tags': [], 'country': '', 'mb': ''}          # not in MusicBrainz: remembered, so it is not asked again


def _enrich_job(todo):
    with _lock:
        _job.update(running=True, done=0, total=len(todo), started=time.time())
    try:
        tags = _load()
        for i, (aid, name) in enumerate(todo):
            try:
                res = _mb_lookup(name)
            except Exception:
                res = None
                time.sleep(3)
            if res is not None:
                tags[aid] = dict(res, n=name, at=int(time.time()))
            _job['done'] = i + 1
            if (i + 1) % 20 == 0:
                _save(tags)
            time.sleep(_MB_GAP)
        _save(tags)
    finally:
        _job['running'] = False


def _pending(tracks, tags):
    names = {}
    for t in tracks:
        for c in (t.get('as') or []):
            if isinstance(c, (list, tuple)) and len(c) > 1 and c[0] not in tags:
                names.setdefault(c[0], c[1])
    return list(names.items())


def _start_enrich():
    with _lock:
        if _job['running']:
            return False
        todo = _pending(_tracks(), _load())
        if not todo:
            return False
        _job['running'] = True
    threading.Thread(target=_enrich_job, args=(todo,), daemon=True).start()
    return True


# ─── 2. understanding the question ─────────────────────────────────────────────────────────────

_SCHEMA = {
    'type': 'object',
    'properties': {
        'any_tags': {'type': 'array', 'items': {'type': 'string'}},
        'not_tags': {'type': 'array', 'items': {'type': 'string'}},
        'artists': {'type': 'array', 'items': {'type': 'string'}},
        'words': {'type': 'array', 'items': {'type': 'string'}},
        'year_from': {'type': ['integer', 'null']},
        'year_to': {'type': ['integer', 'null']},
        'liked': {'type': 'boolean'},
        'unplayed': {'type': 'boolean'},
        'sort': {'type': 'string', 'enum': ['', 'recent', 'popular']},
    },
    'required': ['any_tags', 'not_tags', 'artists', 'words', 'year_from', 'year_to', 'liked', 'unplayed', 'sort'],
}

_PROMPT = """You turn a request about a personal music library into a search filter. Answer with JSON only.
The library has these tags (genres, languages, countries): {vocab}

Fields:
- any_tags: tags from the list above that the songs should have (any one is enough). Pick every tag that fits the request. Only use tags from the list; if nothing in the list fits a word of the request, leave any_tags empty and put that word in words.
- not_tags: tags the songs must NOT have ("but not trap").
- artists: artist names the request names.
- words: other words that must appear in the title or album.
- year_from / year_to: release years, null if not asked ("2010s" -> 2010 and 2019).
- liked: true only if the request asks for liked, favourite or hearted songs.
- unplayed: true only if it asks for songs not played yet or never played.
- sort: "recent" for newly added, "popular" for most played, else "".
Words like show, me, all, songs, tracks, i, ive, got, have, my, play, find are not search terms."""


def _ollama_filter(q, vocab):
    r = requests.post('%s/api/chat' % shared.OLLAMA_URL, timeout=90, json={
        'model': _MODEL, 'stream': False, 'format': _SCHEMA, 'keep_alive': '30m',
        'options': {'temperature': 0, 'num_ctx': 2048, 'num_predict': 160},
        'messages': [{'role': 'system', 'content': _PROMPT.format(vocab=', '.join(vocab[:90]))}, {'role': 'user', 'content': q}]})
    r.raise_for_status()
    return json.loads(r.json()['message']['content'])


_STOP = set('show me all the songs song tracks track i ive i\'ve got have my play find music of by from that with and some any a an in on to list give'.split())


def _plain_filter(q, vocab):
    """No model: a word (or two words) that names a tag selects that tag, and each such word must be satisfied; the rest must appear in the title, album or artist."""
    words = [w for w in _norm(q).split() if w not in _STOP and w != 'but']
    flat = {v: v.replace('-', ' ') for v in vocab}
    groups, rest, nots, neg, i = [], [], [], False, 0
    while i < len(words):
        if words[i] in ('not', 'without', 'except', 'excluding', 'no'):
            neg = True
            i += 1
            continue
        two = ' '.join(words[i:i + 2]) if i + 1 < len(words) else None
        hit = [v for v, fv in flat.items() if two and two == fv] if two else []
        if hit:
            i += 2
        else:
            w = words[i]
            hit = [v for v, fv in flat.items() if w == fv or w in fv.split()]
            i += 1
        if hit and neg:
            nots += hit
        elif hit:
            groups.append(hit)
        elif not neg:
            rest.append(words[i - 1])
        neg = False
    return {'any_tags': groups[0] if groups else [], 'groups': groups[1:], 'not_tags': list(dict.fromkeys(nots)), 'artists': [], 'words': rest, 'year_from': None, 'year_to': None,
            'liked': False, 'unplayed': False, 'sort': ''}


# a question that needs the model: negation, a range of years, flags, sorting. Anything plainer is answered by the tags at once.
_NEEDS_MODEL = re.compile(r"\b(not|but|without|except|excluding|no|before|after|since|between|older|newer|oldest|newest|recent|recently|latest|liked|likes?|favou?rites?|never|unplayed|"
                          r"most|popular|top|haven'?t|didn'?t)\b|\b(19|20)\d\d\b|\b\d0s\b", re.I)


_LIKED = re.compile(r'\b(like[ds]?|favou?rites?|hearted|loved?)\b')
_UNPLAYED = re.compile(r"\b(never|not|haven'?t|unplayed|yet)\b.*\bplayed\b|\bunplayed\b|\bnever (heard|listened)")
_RECENT = re.compile(r'\b(recent(ly)?|new(est)?|latest|just added|added)\b')
_POPULAR = re.compile(r'\b(most played|popular|top|most listened|favou?rite)\b')


def _clean(f, vocab, q=None):
    """Only what the vocabulary and the sentence back up: a small model sometimes ticks "liked" for any question."""
    vs = set(vocab)
    ql = (q or '').lower()

    def tags(xs):
        out = []
        for x in (xs or []):
            x = _norm(x)
            out += [x] if x in vs else [v for v in vocab if x and (x in v.split() or v in x.split())][:3]
        return list(dict.fromkeys(out))

    def num(v):
        return v if isinstance(v, int) and 1900 <= v <= 2100 else None
    return {'any_tags': tags(f.get('any_tags')), 'groups': [g for g in (tags(x) for x in (f.get('groups') or [])[:4]) if g], 'not_tags': tags(f.get('not_tags')),
            'artists': [_norm(a) for a in (f.get('artists') or []) if _norm(a)][:5], 'words': [_norm(w) for w in (f.get('words') or []) if _norm(w) and _norm(w) not in _STOP][:6],
            'year_from': num(f.get('year_from')), 'year_to': num(f.get('year_to')),
            'liked': f.get('liked') is True and (q is None or bool(_LIKED.search(ql))),
            'unplayed': f.get('unplayed') is True and (q is None or bool(_UNPLAYED.search(ql))),
            'sort': f.get('sort') if f.get('sort') in ('recent', 'popular') and (q is None or bool((_RECENT if f.get('sort') == 'recent' else _POPULAR).search(ql))) else ''}


def _apply(f, tracks, tags):
    out = []
    for t in tracks:
        tt = _track_tags(t, tags)
        if f['any_tags'] and not any(x in tt for x in f['any_tags']):
            continue
        if any(not any(x in tt for x in g) for g in f.get('groups', [])):
            continue
        if f['not_tags'] and any(x in tt for x in f['not_tags']):
            continue
        names = _norm(' '.join(c[1] for c in (t.get('as') or []) if len(c) > 1) or t.get('ar'))
        if f['artists'] and not any(a in names for a in f['artists']):
            continue
        hay = _norm('%s %s %s' % (t.get('t', ''), t.get('al', ''), names))
        if f['words'] and not all(w in hay for w in f['words']):
            continue
        y = int(t['y']) if str(t.get('y') or '').isdigit() else None
        if f['year_from'] and (y is None or y < f['year_from']):
            continue
        if f['year_to'] and (y is None or y > f['year_to']):
            continue
        if f['liked'] and not t.get('fav'):
            continue
        if f['unplayed'] and t.get('pc'):
            continue
        out.append(t)
    if f['sort'] == 'popular':
        out.sort(key=lambda t: -(t.get('pc') or 0))
    elif f['sort'] == 'recent':
        out.sort(key=lambda t: -(t.get('a') or 0))
    else:
        out.sort(key=lambda t: (_norm(t.get('ar')), _norm(t.get('al')), t.get('n') or 0))
    return out


def _describe(f):
    bits = []
    for g in ([f['any_tags']] if f['any_tags'] else []) + list(f.get('groups', [])):
        bits.append(' / '.join(g[:3]))
    if f['not_tags']:
        bits.append('not ' + ', '.join(f['not_tags'][:3]))
    if f['artists']:
        bits.append('by ' + ', '.join(f['artists']))
    if f['words']:
        bits.append('“%s”' % ' '.join(f['words']))
    if f['year_from'] or f['year_to']:
        bits.append('%s–%s' % (f['year_from'] or '', f['year_to'] or ''))
    if f['liked']:
        bits.append('liked')
    if f['unplayed']:
        bits.append('not played yet')
    if f['sort']:
        bits.append('most played' if f['sort'] == 'popular' else 'newest first')
    return ' · '.join(bits) or 'everything'


def _answer(q):
    t0 = time.time()
    tracks = _tracks()
    tags = _load()
    started = _start_enrich()
    vocab = _vocab(tracks, tags)
    how = 'tags'
    f = _clean(_plain_filter(q, vocab), vocab, q)
    phrase = ' '.join(w for w in _norm(q).split() if w not in _STOP)
    if ' ' in phrase and any(phrase in _norm(c[1]) for t in tracks for c in (t.get('as') or []) if len(c) > 1):
        f = _clean({'artists': [phrase]}, vocab, q)                      # "daft punk" is an artist, not the punk tag
    plain_ok = bool(f['any_tags'] or f['groups'] or f['words'] or f['artists'])
    if _NEEDS_MODEL.search(q) or not plain_ok:
        key = q.lower()
        if key in _cache:
            f, how = _cache[key], 'model'
        else:
            try:
                f = _clean(_ollama_filter(q, vocab), vocab, q)
                how = 'model'
                if len(_cache) > 200:
                    _cache.clear()
                _cache[key] = f
            except Exception:
                f, how = _clean(_plain_filter(q, vocab), vocab, q), 'words'
    if how == 'model' and not (f['any_tags'] or f['groups'] or f['not_tags'] or f['artists'] or f['words'] or f['year_from'] or f['year_to'] or f['liked'] or f['unplayed'] or f['sort']):
        f, how = _clean(_plain_filter(q, vocab), vocab, q), 'words'                    # the model found nothing in it: the word match still can
    hits = _apply(f, tracks, tags)
    return {'ok': True, 'q': q, 'how': how, 'understood': _describe(f), 'filter': f, 'ids': [t['f'] for t in hits][:3000], 'n': len(hits),
            'learning': dict(_job) if _job['running'] else None, 'ms': int((time.time() - t0) * 1000)}


@bp.route('/api/music/ask')
@limiter.limit('30 per minute')
def music_ask():
    q = (request.args.get('q') or '').strip()[:200]
    if len(q) < 2:
        return jsonify({'error': 'ask something'}), 400
    return jsonify(_answer(q))


@bp.route('/api/music/ask/warm')
def music_ask_warm():
    """Load the model into memory ahead of the question (the client asks when someone starts typing a sentence), so the answer does not wait for it."""
    def go():
        try:
            requests.post('%s/api/generate' % shared.OLLAMA_URL, json={'model': _MODEL, 'prompt': '', 'keep_alive': '30m'}, timeout=120)
        except Exception:
            pass
    threading.Thread(target=go, daemon=True).start()
    _start_enrich()                                       # and begin tagging the artists, if that is not done yet
    return jsonify({'ok': True})


@bp.route('/api/music/ask/status')
def music_ask_status():
    tracks, tags = _tracks(), _load()
    todo = len(_pending(tracks, tags))
    return jsonify({'artists_tagged': len(tags), 'artists_left': todo, 'job': dict(_job), 'model': _MODEL})


def _boot_tagging():
    if _start_enrich():
        print('[ask] tagging artists from MusicBrainz in the background', flush=True)


if 'pytest' not in __import__('sys').modules:                  # a minute after the server starts, pick up where the tagging stopped (nothing to do once it is finished)
    _t = threading.Timer(60, _boot_tagging)
    _t.daemon = True
    _t.start()
