"""Music player routes."""
from flask import Blueprint, jsonify, request, send_file, Response, stream_with_context
import subprocess
from pathlib import Path
from shared import MUSIC_EXTS
import hashlib
import itertools
import json
import secrets
import datetime
import difflib
import requests
import os
import re
import shutil
import threading
import time

import shared
from shared import limiter

from routes import playlists_local as _lp

bp = Blueprint('music', __name__)

# Cache directory for extracted + cropped artwork.
# Resolved at request time so path changes apply immediately.
def _artwork_cache():
    cache = shared.MUSIC_DIR / '.artwork_cache'
    try:
        cache.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        pass  # read-only fs. Music app will show empty state
    return cache


def _artwork_cache_path(filename):
    """Return cached square artwork path, creating it if needed."""
    key = hashlib.md5(filename.encode()).hexdigest()[:12]
    return _artwork_cache() / f'{key}.png'


@bp.route('/api/music/list')
def music_list():
    """List all music files in the music directory."""
    songs = []
    if shared.MUSIC_DIR.exists():
        for f in sorted(shared.MUSIC_DIR.iterdir()):
            if f.suffix.lower() in MUSIC_EXTS:
                size_mb = f.stat().st_size / (1024 * 1024)
                songs.append({
                    'name': f.stem,
                    'filename': f.name,
                    'ext': f.suffix.lower().lstrip('.'),
                    'size_mb': round(size_mb, 1),
                })
    return jsonify(songs)


def _safe_music_path(filename):
    """Resolve a music file path and ensure it stays within MUSIC_DIR."""
    base = shared.MUSIC_DIR.resolve()
    candidate = (shared.MUSIC_DIR / filename).resolve()
    try:
        if candidate.is_relative_to(base):
            return candidate
    except AttributeError:
        if os.path.commonpath([str(base), str(candidate)]) == str(base):
            return candidate
    return None


def _local_src(ident):
    """The file of a song on this machine: a path in file mode, or (with Navidrome) the path Navidrome reported for that id. None when it is not
    here (another machine, a different mount, moved since the last scan): the caller then asks Navidrome for the bytes as before."""
    rel = _nd_paths.get(ident) if _nd_conf() else ident
    if not rel:
        return None
    p = _safe_music_path(rel)
    return p if p and p.is_file() else None


def _file_stream(filename):
    """Stream a music file. Uses Flask send_file which handles
    HTTP Range requests natively for fast seeking on iOS."""
    filepath = _safe_music_path(filename)
    if not filepath or not filepath.is_file():
        return jsonify({'error': 'Not found'}), 404

    mime_types = {
        '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.flac': 'audio/flac',
        '.ogg': 'audio/ogg', '.m4a': 'audio/mp4', '.aac': 'audio/aac',
        '.opus': 'audio/ogg', '.oga': 'audio/ogg', '.m4b': 'audio/mp4', '.mp4': 'audio/mp4',
    }
    mime = mime_types.get(filepath.suffix.lower(), 'application/octet-stream')

    resp = send_file(str(filepath), mimetype=mime)
    resp.headers['Accept-Ranges'] = 'bytes'
    return resp


def _file_artwork(filename):
    """Extract embedded artwork, crop to square, cache it."""
    filepath = _safe_music_path(filename)
    if not filepath or not filepath.is_file():
        return jsonify({'error': 'Not found'}), 404

    cache_path = _artwork_cache_path(filename)
    none_marker = cache_path.with_suffix('.none')

    def _art_response():
        resp = send_file(str(cache_path), mimetype='image/png')
        # /api/ responses default to no-store; artwork is immutable and heavy
        resp.headers['Cache-Control'] = 'private, max-age=86400'
        return resp

    # Serve from cache if exists
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return _art_response()
    if none_marker.exists():
        resp = jsonify({'error': 'No artwork'})
        resp.headers['Cache-Control'] = 'private, max-age=3600'
        return resp, 404

    # Extract + crop to square in one ffmpeg pass (first video/cover stream)
    try:
        subprocess.run(
            [
                'ffmpeg', '-y', '-i', str(filepath),
                '-map', '0:v:0',
                '-vf', 'crop=min(iw\\,ih):min(iw\\,ih),scale=256:256',
                '-frames:v', '1',
                str(cache_path),
            ],
            capture_output=True, timeout=8
        )
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return _art_response()
        try:
            cache_path.unlink()
        except OSError:
            pass
        try:
            none_marker.touch()
        except OSError:
            pass
        return jsonify({'error': 'No artwork'}), 404
    except Exception:
        return jsonify({'error': 'Failed'}), 500


# ─── Library index (tags, cached) ────────────────────────────────────────
# One recursive scan with mutagen, cached on disk by (mtime, size) so only new
# or changed files are re-read. Falls back to "NN - Artist - Title" filenames.
_APP_DIR = Path(__file__).resolve().parent.parent
_INDEX_FILE = _APP_DIR / 'music_index.json'
_STATE_FILE = _APP_DIR / 'music_state.json'   # favorites + play counts
_index_lock = threading.Lock()
_state_lock = threading.Lock()
_FILENAME_RE = re.compile(r'^(?:\d+\s*-\s*)?(.+?)\s+-\s+(.+)$')


def _first(tags, key):
    v = tags.get(key) if tags else None
    return (v[0] if isinstance(v, list) and v else v or '') if tags else ''


def _read_track(path, rel):
    title = artist = album = genre = year = ''
    track = 0
    dur = 0.0
    try:
        import mutagen
        m = mutagen.File(str(path), easy=True)
        if m is not None:
            dur = float(getattr(m.info, 'length', 0) or 0)
            title = str(_first(m.tags, 'title')).strip()
            artist = str(_first(m.tags, 'artist')).strip()
            album = str(_first(m.tags, 'album')).strip()
            genre = str(_first(m.tags, 'genre')).strip()
            year = str(_first(m.tags, 'date')).strip()[:4]
            tn = str(_first(m.tags, 'tracknumber')).split('/')[0]
            track = int(tn) if tn.isdigit() else 0
    except Exception:
        pass
    if not title or not artist:
        mt = _FILENAME_RE.match(path.stem)
        if mt:
            artist = artist or mt.group(1).strip()
            title = title or mt.group(2).strip()
        else:
            title = title or path.stem
    # "Various Artists"-style albums keep per-track artist; fine as is.
    return {'f': rel, 't': title, 'ar': artist or 'Unknown Artist', 'al': album,
            'g': genre, 'y': year, 'n': track, 'd': round(dur, 1)}


# The tag index is built in the background: the first scan of a big library took minutes (every file is opened), and the first request waited for all
# of it. Now a request gets the library at once (songs not read yet show what their file name says) while a thread reads the tags and fills them in.
_idx_mem = {}                                               # rel path -> {'k': [mtime, size], 'r': record}: what has been read so far
_scan = {'running': False, 'left': 0}


def _placeholder(path, rel):
    """What a song looks like before its tags are read: title and artist from the file name."""
    title, artist = path.stem, ''
    mt = _FILENAME_RE.match(path.stem)
    if mt:
        artist, title = mt.group(1).strip(), mt.group(2).strip()
    return {'f': rel, 't': title, 'ar': artist or 'Unknown Artist', 'al': '', 'g': '', 'y': '', 'n': 0, 'd': 0}


def _save_index():
    try:
        tmp = _INDEX_FILE.with_suffix('.tmp')
        with _index_lock:
            data = dict(_idx_mem)
        tmp.write_text(json.dumps(data))
        tmp.replace(_INDEX_FILE)
    except OSError:
        pass


def _scan_tags(todo):
    """Background thread: read the tags of the songs not yet in the index."""
    try:
        done = 0
        for p, rel, key in todo:
            rec = _read_track(p, rel)
            with _index_lock:
                _idx_mem[rel] = {'k': key, 'r': rec}
            done += 1
            _scan['left'] = len(todo) - done
            if done % 100 == 0:
                _save_index()
        _save_index()
    finally:
        _scan['running'] = False
        _scan['left'] = 0
        _invalidate()                                       # the next library request has the real tags


def _build_index():
    base = shared.MUSIC_DIR
    with _index_lock:
        if not _idx_mem or _idx_mem.get('_dir') != str(base):
            try:
                disk = json.loads(_INDEX_FILE.read_text()) if _INDEX_FILE.exists() else {}
            except Exception:
                disk = {}
            _idx_mem.clear()
            if disk.get('_dir') == str(base):
                _idx_mem.update(disk)
            _idx_mem['_dir'] = str(base)
    out, fresh, todo = [], {}, []
    if base.exists():
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for name in files:
                p = Path(root) / name
                if p.suffix.lower() not in MUSIC_EXTS or name.startswith('.'):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                rel = str(p.relative_to(base))
                key = [st.st_mtime, st.st_size]
                with _index_lock:
                    hit = _idx_mem.get(rel)
                if hit and hit.get('k') == key:
                    rec = hit['r']
                    fresh[rel] = hit
                else:
                    rec = _placeholder(p, rel)
                    todo.append((p, rel, key))
                out.append(dict(rec, a=int(st.st_mtime)))
    with _index_lock:                                       # forget songs that were deleted
        pending = {t[1] for t in todo}
        for k in [k for k in _idx_mem if k != '_dir' and k not in fresh and k not in pending]:
            _idx_mem.pop(k, None)
    if todo and not _scan['running']:
        _scan.update(running=True, left=len(todo))
        threading.Thread(target=_scan_tags, args=(todo,), daemon=True).start()
    elif not todo:
        _scan['left'] = 0
    out.sort(key=lambda r: (r['ar'].lower(), r['al'].lower(), r['n'], r['t'].lower()))
    return out


def _load_state():
    try:
        return json.loads(_STATE_FILE.read_text())
    except Exception:
        return {'favs': [], 'plays': {}}


def _save_state(st):
    tmp = _STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(st))
    tmp.replace(_STATE_FILE)



# ─── Navidrome / Subsonic (optional: used when credentials are set, otherwise the music folder is read directly) ──
# Tags, covers, stars and play counts then come from Navidrome. Credentials stay server-side; streams and covers are proxied
# so the browser only ever talks to reclmr. Without credentials the file-tag
# index above is used instead.
_nd_cache = {'ts': 0, 'data': None}
_nd_lock = threading.Lock()
_ND_TTL = 20


def _nd_conf():
    user = os.environ.get('RECLMR_NAVIDROME_USER', '')
    pw = os.environ.get('RECLMR_NAVIDROME_PASS', '')
    base = os.environ.get('RECLMR_NAVIDROME_URL', 'http://127.0.0.1:4533/navidrome').rstrip('/')
    return (base, user, pw) if user and pw else None


def _nd_params(conf, extra=None):
    base, user, pw = conf
    salt = secrets.token_hex(6)
    p = {'u': user, 't': hashlib.md5((pw + salt).encode()).hexdigest(), 's': salt,
         'v': '1.16.1', 'c': 'reclmr', 'f': 'json'}
    p.update(extra or {})
    return p


def _nd_get(endpoint, **params):
    conf = _nd_conf()
    if not conf:
        raise RuntimeError('Navidrome is not configured')
    r = requests.get(f'{conf[0]}/rest/{endpoint}.view', params=_nd_params(conf, params), timeout=30)
    r.raise_for_status()
    j = r.json().get('subsonic-response', {})
    if j.get('status') != 'ok':
        raise RuntimeError((j.get('error') or {}).get('message', 'Navidrome error'))
    return j


def _epoch(iso):
    if not iso:
        return 0
    try:
        return int(datetime.datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp())
    except ValueError:
        return 0


_nd_paths = {}      # Navidrome song id -> path inside the music folder, filled whenever the library is read: lets a song be played from the file itself
_walk = {'at': 0.0, 'by': {}}


def _local_sizes():
    """{(size in bytes, extension): [paths]} of the music folder, from a walk that only stats files (no tags are read), kept for 5 minutes."""
    now = time.time()
    if _walk['by'] and now - _walk['at'] < 300:
        return _walk['by']
    base, by = shared.MUSIC_DIR, {}
    if base.exists():
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext in MUSIC_EXTS and not name.startswith('.'):
                    try:
                        by.setdefault((os.stat(os.path.join(root, name)).st_size, ext), []).append(os.path.relpath(os.path.join(root, name), base))
                    except OSError:
                        pass
    _walk.update(at=now, by=by)
    return by


def _key(text):
    return re.sub(r'[^a-z0-9]+', '', (text or '').lower())


def _nd_local_paths(tracks):
    """Which file on this machine each Navidrome song is. Navidrome's own `path` is tried first (it is the real one on some setups; on others it is a
    made-up Artist/Album/Title), then the file size: Navidrome reports the exact size in bytes, and a file of the same size and type is the same
    file. A song that cannot be placed is simply not here: it plays through Navidrome as before."""
    by = _local_sizes()
    out = {}
    for t in tracks:
        rel = t['p'] if t.get('p') and (_safe_music_path(t['p']) or Path('/nonexistent')).is_file() else None
        if not rel and t.get('sz') and t.get('sx'):
            cands = by.get((int(t['sz']), '.' + str(t['sx']).lower()), [])
            if len(cands) == 1:
                rel = cands[0]
            elif cands:                                       # several files of exactly that size (copies): the one named like the song
                k = _key(t.get('t'))
                rel = next((c for c in cands if k and k in _key(Path(c).stem)), None)
        if rel:
            out[t['f']] = rel
    return out


def _nd_song(s):
    path = s.get('path') or ''
    base = str(shared.MUSIC_DIR).rstrip('/') + '/'
    if path.startswith(base):
        path = path[len(base):]
    genre = s.get('genre') or (s.get('genres') or [{}])[0].get('name', '')
    d = {
        'f': s['id'], 't': s.get('title') or '', 'ar': s.get('artist') or 'Unknown Artist',
        'ai': s.get('artistId') or s.get('artist') or '', 'al': s.get('album') or '',
        'as': [[a['id'], a['name']] for a in (s.get('artists') or []) if a.get('id') and a.get('name')],   # every credited artist, not just the first
        'li': s.get('albumId') or '', 'aa': s.get('displayAlbumArtist') or s.get('albumArtist') or '',
        'y': str(s.get('year') or ''), 'g': genre, 'n': s.get('track') or 0,
        'dn': s.get('discNumber') or 1, 'd': s.get('duration') or 0,
        'a': _epoch(s.get('created')), 'c': s.get('coverArt') or '', 'p': path,
        'fav': bool(s.get('starred')), 'pc': s.get('playCount') or 0,
        'lp': _epoch(s.get('played')), 'br': s.get('bitRate') or 0, 'sx': s.get('suffix') or '',
        'sr': s.get('samplingRate') or 0, 'bd': s.get('bitDepth') or 0, 'sz': s.get('size') or 0, 'ch': s.get('channelCount') or 0,
    }
    gs = [g['name'] for g in (s.get('genres') or []) if g.get('name')]
    if len(gs) > 1:
        d['gs'] = gs                                         # every genre tag, so search and the Genres list see more than the first
    if s.get('explicitStatus') == 'explicit':
        d['ex'] = 1                                          # the E badge
    co = [[c['artist']['id'], c['artist']['name'], str(c.get('role') or '')] for c in (s.get('contributors') or [])
          if isinstance(c.get('artist'), dict) and c['artist'].get('id') and c['artist'].get('name')]
    if co:
        d['co'] = co                                         # composer, lyricist...: [artist id, name, role], for the Credits card
    return d


def _nd_library():
    songs, off, page = [], 0, 500
    for q in ('', '""'):
        songs, off = [], 0
        while off < 200000:
            res = _nd_get('search3', query=q, artistCount=0, albumCount=0,
                          songCount=page, songOffset=off).get('searchResult3', {})
            got = res.get('song', [])
            songs.extend(got)
            if len(got) < page:
                break
            off += page
        if songs:
            break
    tracks = [_nd_song(s) for s in songs if s.get('id')]
    global _nd_paths
    _nd_paths = _nd_local_paths(tracks)                        # (replaced whole, so a song being requested never finds it half filled)
    try:
        pls = _nd_get('getPlaylists').get('playlists', {}).get('playlist', [])
        playlists = [{'id': p['id'], 'name': p.get('name', ''), 'n': p.get('songCount', 0),
                      'c': p.get('coverArt', ''), 'd': p.get('duration', 0),
                      'u': _epoch(p.get('changed') or p.get('created'))} for p in pls]
    except Exception:
        playlists = []
    return {'source': 'navidrome', 'tracks': tracks, 'playlists': playlists}


def _file_playlists(tracks):
    pls = _lp.listing({t['f']: t['d'] for t in tracks})
    for p in pls:
        f = _pl_cover_file(p['id'])
        if f.exists():
            p['c'] = 'pl-%s_%d' % (p['id'], int(f.stat().st_mtime))      # the picture the user gave it (served by music_artwork)
    return pls


def _file_library():
    recs = _build_index()
    with _state_lock:
        st = _load_state()
    favs, plays = set(st.get('favs', [])), st.get('plays', {})
    tracks = []
    for r in recs:
        folder = r['f'].rsplit('/', 1)[0] if '/' in r['f'] else ''
        n, last = plays.get(r['f'], [0, 0])
        tracks.append({
            'f': r['f'], 't': r['t'], 'ar': r['ar'], 'ai': r['ar'], 'al': r['al'],
            'li': (folder + '||' + r['al'].lower()) if r['al'] else '', 'aa': '',
            'y': r['y'], 'g': r['g'], 'n': r['n'], 'dn': 1, 'd': r['d'], 'a': r['a'],
            'c': r['f'], 'p': r['f'], 'fav': r['f'] in favs, 'pc': n, 'lp': last,
            'br': 0, 'sx': r['f'].rsplit('.', 1)[-1],
        })
    return {'source': 'files', 'tracks': tracks, 'playlists': _file_playlists(tracks), 'scanning': _scan['left'] if _scan['running'] else 0}


def _library_data():
    """The whole library (Navidrome if configured, else file tags), cached briefly."""
    now = time.time()
    with _nd_lock:
        if _nd_cache['data'] and now - _nd_cache['ts'] < _ND_TTL:
            return _nd_cache['data']
    error = ''
    data = None
    if _nd_conf():
        try:
            data = _nd_library()
        except Exception as e:
            error = str(e)
    if data is None:
        data = _file_library()
        if error:
            data['error'] = 'Navidrome unavailable (' + error + '). Showing file tags'
    elif not data['tracks']:
        data['error'] = 'Navidrome returned no songs'
    if not error and not data.get('scanning'):
        with _nd_lock:
            _nd_cache.update(ts=now, data=data)
    return data


@bp.route('/api/music/library')
def music_library():
    """Whole library in one request. `fresh=1` (pull to refresh) drops the server's saved copy first."""
    if request.args.get('fresh'):
        _invalidate()
    return jsonify(_library_data())


@bp.route('/api/music/meta')
def music_meta():
    """Title, artist, album, length and cover id for a few tracks (used by the desktop media-widget companion)."""
    ids = [i for i in (request.args.get('ids') or '').split(',') if i][:20]
    want = set(ids)
    out = {}
    for t in _library_data().get('tracks', []):
        if t['f'] in want:
            out[t['f']] = {'t': t['t'], 'ar': t['ar'], 'al': t['al'], 'd': t['d'], 'c': t['c']}
    return jsonify(out)


def _invalidate():
    with _nd_lock:
        _nd_cache.update(ts=0, data=None)


@bp.route('/api/music/playlists', methods=['POST'])
def music_playlist_create():
    """Create a Navidrome playlist, optionally seeded with one track."""
    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip()[:120]
    ident = data.get('id')
    ids = data.get('ids')
    if ids is not None and (not isinstance(ids, list) or len(ids) > 5000 or any(_bad_id(i) for i in ids)):
        return jsonify({'error': 'bad request'}), 400
    if not name or (ident and _bad_id(ident)):
        return jsonify({'error': 'bad request'}), 400
    if not _nd_conf():                                      # no Navidrome: a playlist is a .m3u8 file (routes/playlists_local.py)
        pid = _lp.create(name, ids if ids else ([ident] if ident else []))
        _invalidate()
        return jsonify({'ok': True, 'id': pid, 'name': name})
    try:
        params = {'name': name}
        if ids:                                             # a whole list at once (used to bring back a deleted playlist)
            params['songId'] = ids
        elif ident:
            params['songId'] = ident
        pl = _nd_get('createPlaylist', **params).get('playlist') or {}
    except Exception as e:
        return jsonify({'error': str(e)}), 502
    _invalidate()
    return jsonify({'ok': True, 'id': pl.get('id', ''), 'name': name})


@bp.route('/api/music/playlist/<pid>/rename', methods=['POST'])
def music_playlist_rename(pid):
    """Give a playlist a new name."""
    name = str((request.get_json(silent=True) or {}).get('name') or '').strip()[:120]
    if _bad_id(pid) or not name:
        return jsonify({'error': 'bad request'}), 400
    if not _nd_conf():
        if not _lp.rename(pid, name):
            return jsonify({'error': 'Playlist not found'}), 404
        _invalidate()
        return jsonify({'ok': True, 'name': name})
    try:
        _nd_get('updatePlaylist', playlistId=pid, name=name)
    except Exception as e:
        return jsonify({'error': str(e)}), 502
    _invalidate()
    return jsonify({'ok': True, 'name': name})


@bp.route('/api/music/playlist/<pid>/delete', methods=['POST'])
def music_playlist_delete(pid):
    """Delete a playlist (only the list: the songs stay in the library)."""
    if _bad_id(pid):
        return jsonify({'error': 'bad request'}), 400
    if not _nd_conf():
        if not _lp.delete(pid):
            return jsonify({'error': 'Playlist not found'}), 404
        _pl_cover_clear(pid)
        _invalidate()
        return jsonify({'ok': True})
    try:
        _nd_get('deletePlaylist', id=pid)
    except Exception as e:
        return jsonify({'error': str(e)}), 502
    _pl_cover_clear(pid)
    _invalidate()
    return jsonify({'ok': True})


def _pl_entries(pid):
    return _nd_get('getPlaylist', id=pid).get('playlist', {}).get('entry', []) or []


@bp.route('/api/music/playlist/<pid>/add', methods=['POST'])
def music_playlist_add(pid):
    """Add a track unless the playlist already has it (`dup: true` then). With `index` it goes in that slot
    (clamped to the end) instead of the end, which is how an undone removal returns to where it was."""
    b = request.get_json(silent=True) or {}
    ident, index = b.get('id'), b.get('index')
    if _bad_id(pid) or _bad_id(ident) or (index is not None and (not isinstance(index, int) or isinstance(index, bool) or index < 0)):
        return jsonify({'error': 'bad id'}), 400
    if not _nd_conf():
        at, found = _lp.add(pid, ident, index)
        if not found:
            return jsonify({'error': 'Playlist or song not found'}), 404
        _invalidate()
        return jsonify({'ok': True, 'dup': True}) if at is None else jsonify({'ok': True, 'dup': False, 'index': at})
    try:
        cur = [e.get('id') for e in _pl_entries(pid)]
        if ident in cur:
            return jsonify({'ok': True, 'dup': True})
        if index is None or index >= len(cur):
            _nd_get('updatePlaylist', playlistId=pid, songIdToAdd=ident)
            at = len(cur)
        else:
            _nd_get('createPlaylist', playlistId=pid, songId=cur[:index] + [ident] + cur[index:])   # replaces the tracks, in the new order
            at = index
    except Exception as e:
        return jsonify({'error': str(e)}), 502
    _invalidate()
    return jsonify({'ok': True, 'dup': False, 'index': at})


@bp.route('/api/music/playlist/<pid>/remove', methods=['POST'])
def music_playlist_remove(pid):
    """Remove every copy of a track from a playlist (Subsonic removes by position, so look them up first)."""
    ident = (request.get_json(silent=True) or {}).get('id')
    if _bad_id(pid) or _bad_id(ident):
        return jsonify({'error': 'bad id'}), 400
    if not _nd_conf():
        idx = _lp.remove(pid, ident)
        if idx is None:
            return jsonify({'error': 'Playlist not found'}), 404
        _invalidate()
        return jsonify({'ok': True, 'removed': len(idx), 'indices': idx})
    try:
        idx = [i for i, e in enumerate(_pl_entries(pid)) if e.get('id') == ident]
        if idx:
            _nd_get('updatePlaylist', playlistId=pid, songIndexToRemove=idx)
    except Exception as e:
        return jsonify({'error': str(e)}), 502
    _invalidate()
    return jsonify({'ok': True, 'removed': len(idx), 'indices': idx})


@bp.route('/api/music/playlist/<pid>/order', methods=['POST'])
def music_playlist_order(pid):
    """Save an edited playlist: the tracks in their new order, with any the user removed left out.
    `base` is how many tracks the page started from. Refused (409) if the playlist changed since, or if
    `ids` would add something it doesn't have, so a stale page can never drop or resurrect tracks."""
    b = request.get_json(silent=True) or {}
    ids, base = b.get('ids'), b.get('base')
    if (_bad_id(pid) or not isinstance(ids, list) or len(ids) > 5000 or any(_bad_id(i) for i in ids)
            or not isinstance(base, int) or isinstance(base, bool)):
        return jsonify({'error': 'bad request'}), 400
    if not _nd_conf():
        res = _lp.set_order(pid, ids, base)
        if res == 'missing':
            return jsonify({'error': 'Playlist not found'}), 404
        if res == 'stale':
            return jsonify({'error': 'The playlist changed elsewhere', 'stale': True}), 409
        _invalidate()
        return jsonify({'ok': True})
    try:
        from collections import Counter
        cur = [e.get('id') for e in _pl_entries(pid)]
        if len(cur) != base or Counter(ids) - Counter(cur):
            return jsonify({'error': 'The playlist changed elsewhere', 'stale': True}), 409
        if not ids:
            if cur:
                _nd_get('updatePlaylist', playlistId=pid, songIndexToRemove=list(range(len(cur))))
        else:
            _nd_get('createPlaylist', playlistId=pid, songId=ids)      # with playlistId this replaces the tracks of that playlist
    except Exception as e:
        return jsonify({'error': str(e)}), 502
    _invalidate()
    return jsonify({'ok': True})


@bp.route('/api/music/membership')
def music_membership():
    """Ids of the playlists that contain a track."""
    ident = request.args.get('id', '')
    if _bad_id(ident):
        return jsonify({'error': 'bad id'}), 400
    if not _nd_conf():
        return jsonify({'playlists': _lp.membership(ident)})
    try:
        pls = _nd_get('getPlaylists').get('playlists', {}).get('playlist', []) or []
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as ex:
            found = list(ex.map(lambda p: p['id'] if any(e.get('id') == ident for e in _pl_entries(p['id'])) else None, pls))
    except Exception as e:
        return jsonify({'error': str(e)}), 502
    return jsonify({'playlists': [i for i in found if i]})


@bp.route('/api/music/inplaylists')
def music_inplaylists():
    """Ids of every track that is in at least one playlist (for the tick on Now Playing)."""
    if not _nd_conf():
        return jsonify({'ids': _lp.in_any()})
    try:
        pls = _nd_get('getPlaylists').get('playlists', {}).get('playlist', []) or []
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as ex:
            lists = list(ex.map(lambda p: [e['id'] for e in _pl_entries(p['id']) if e.get('id')], pls))
    except Exception as e:
        return jsonify({'error': str(e)}), 502
    return jsonify({'ids': sorted({i for l in lists for i in l})})


@bp.route('/api/music/playlist/<pid>')
def music_playlist(pid):
    if not _nd_conf():
        ids = _lp.entries(pid)
        if ids is None:
            return jsonify({'error': 'Playlist not found'}), 404
        return jsonify({'ids': ids})
    try:
        entries = _nd_get('getPlaylist', id=pid).get('playlist', {}).get('entry', [])
        return jsonify({'ids': [e['id'] for e in entries if e.get('id')]})
    except Exception as e:
        return jsonify({'error': str(e)}), 502


def _bad_id(ident):
    return not isinstance(ident, str) or not ident or len(ident) > 600


@bp.route('/api/music/favorite', methods=['POST'])
def music_favorite():
    data = request.get_json(silent=True) or {}
    ident = data.get('id') or data.get('filename')
    if _bad_id(ident):
        return jsonify({'error': 'bad id'}), 400
    on = bool(data.get('on'))
    if _nd_conf():
        try:
            _nd_get('star' if on else 'unstar', id=ident)
        except Exception as e:
            return jsonify({'error': str(e)}), 502
        _invalidate()
        return jsonify({'ok': True, 'on': on})
    if not _safe_music_path(ident):
        return jsonify({'error': 'bad id'}), 400
    with _state_lock:
        st = _load_state()
        favs = [f for f in st.get('favs', []) if f != ident]
        if on:
            favs.append(ident)
        st['favs'] = favs
        _save_state(st)
    _invalidate()
    return jsonify({'ok': True, 'on': on})


@bp.route('/api/music/played', methods=['POST'])
def music_played():
    data = request.get_json(silent=True) or {}
    ident = data.get('id') or data.get('filename')
    if _bad_id(ident):
        return jsonify({'error': 'bad id'}), 400
    if _nd_conf():
        try:
            _nd_get('scrobble', id=ident, submission='true', time=int(time.time() * 1000))
        except Exception as e:
            return jsonify({'error': str(e)}), 502
        _invalidate()
        return jsonify({'ok': True})
    if not _safe_music_path(ident):
        return jsonify({'error': 'bad id'}), 400
    with _state_lock:
        st = _load_state()
        n, _ = st.setdefault('plays', {}).get(ident, [0, 0])
        st['plays'][ident] = [n + 1, int(time.time())]
        _save_state(st)
    _invalidate()
    return jsonify({'ok': True})


_PASS_HEADERS = ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges', 'Last-Modified', 'ETag')


def _nd_proxy(endpoint, params, extra_headers=None, cache=None, ctype=None):
    """Stream a Navidrome response through reclmr (Range-aware)."""
    conf = _nd_conf()
    headers = dict(extra_headers or {})
    rng = request.headers.get('Range')
    if rng:
        headers['Range'] = rng
    try:
        up = requests.get(f'{conf[0]}/rest/{endpoint}.view', params=_nd_params(conf, params),
                          headers=headers, stream=True, timeout=(5, 60))
    except requests.RequestException:
        return jsonify({'error': 'Navidrome unreachable'}), 502
    ctype = up.headers.get('Content-Type', '')
    if up.status_code >= 400 or 'json' in ctype or 'xml' in ctype:  # Subsonic reports errors as JSON/XML
        up.close()
        return jsonify({'error': 'Not found'}), 404

    def gen():
        try:
            for chunk in up.iter_content(65536):
                yield chunk
        finally:
            up.close()

    resp = Response(stream_with_context(gen()), status=up.status_code)
    for h in _PASS_HEADERS:
        if h in up.headers:
            resp.headers[h] = up.headers[h]
    if ctype:
        resp.headers['Content-Type'] = ctype
    if cache:
        resp.headers['Cache-Control'] = cache
    return resp


# ─── Streaming quality: lower-bitrate copies of songs, made once and kept ───────────
# Navidrome's own transcoded stream cannot be seeked (no Range), so the MP3 is fetched whole, cached on disk and served as a normal file.
TRANSCODE_RATES = (320, 256, 192, 160, 128, 96, 64)
_TC_DIR = _APP_DIR / 'transcode_cache'
_tc_locks = {}
_tc_lock = threading.Lock()
_tc_slots = threading.BoundedSemaphore(2)               # at most two songs are converted at the same time
_bg_slot = threading.BoundedSemaphore(1)                # of those, the background "next songs" jobs may use one, never both: playing a song must not queue behind them
_bg_lock = threading.Lock()
_bg_pending = set()


def _tc_limit():
    try:
        return int(os.environ.get('RECLMR_TRANSCODE_CACHE_MB', '2048')) * 1024 * 1024
    except ValueError:
        return 2048 * 1024 * 1024


def _tc_trim(keep=None):
    """Keep the cache under its size: the songs not played for longest go first (never the one just made)."""
    try:
        files = sorted(((f.stat().st_mtime, f.stat().st_size, f) for pat in ('*.mp3', '*.m4a', '*.ogg') for f in _TC_DIR.glob(pat) if f != keep))
    except OSError:
        return
    total, limit = sum(x[1] for x in files) + (keep.stat().st_size if keep is not None and keep.exists() else 0), _tc_limit()
    for _m, size, f in files:
        if total <= limit * 0.9:
            break
        try:
            f.unlink()
            total -= size
        except OSError:
            pass


def _tc_name(ident):
    return re.sub(r'[^A-Za-z0-9_-]', '_', ident)


def _upstream(conf, ident, fmt=None, **kw):
    """Navidrome's stream of a song (`fmt` = None for the file as it is), or None if it is unreachable or answers with an error (Subsonic reports those as JSON/XML)."""
    params = {'id': ident, 'format': 'raw'} if fmt is None else {'id': ident, 'format': 'mp3', 'maxBitRate': fmt}
    try:
        up = requests.get(f'{conf[0]}/rest/stream.view', params=_nd_params(conf, params), stream=True, timeout=(5, 120), **kw)
    except requests.RequestException:
        return None
    ctype = up.headers.get('Content-Type', '')
    if up.status_code >= 400 or 'json' in ctype or 'xml' in ctype:
        up.close()
        return None
    return up


def _save(up, dest):
    with open(dest, 'wb') as out:
        for chunk in up.iter_content(1 << 16):
            out.write(chunk)
    up.close()


def _cached(f, make):
    """The cached file `f`, built by make(path) the first time (once, even when asked for at the same moment; never with the disk nearly full).
    None if it could not be made. A file is only ever put in place whole."""
    if f.exists():
        try:
            os.utime(f, None)                                   # played now: last to be cleared
        except OSError:
            pass
        return f
    with _tc_lock:
        lock = _tc_locks.setdefault(f.name, threading.Lock())
    with lock:
        if f.exists():
            return f
        try:
            _TC_DIR.mkdir(exist_ok=True)
            if shutil.disk_usage(_TC_DIR).free < 2 * 1024 ** 3:
                return None
        except OSError:
            return None
        tmp = f.with_name(f.name + '.part-' + secrets.token_hex(4))
        with _tc_slots:
            try:
                if not make(tmp) or tmp.stat().st_size < 1024:
                    return None
                os.replace(tmp, f)
            except (requests.RequestException, OSError, subprocess.SubprocessError):
                return None
            finally:
                try:
                    tmp.unlink()
                except OSError:
                    pass
    _tc_trim(f)
    return f


def _transcoded(ident, rate):
    """Path of the MP3 of this song at `rate` kbps (made now if it does not exist yet), or None if it could not be made."""
    conf = _nd_conf()
    src = _local_src(ident)
    if src and shutil.which('ffmpeg'):                      # the file is here: convert it with ffmpeg, no round trip through Navidrome
        def make_local(tmp):
            cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-map', '0:a:0', '-vn', '-map_metadata', '-1',
                   '-c:a', 'libmp3lame', '-b:a', f'{rate}k', '-f', 'mp3', str(tmp)]
            return subprocess.run(cmd, capture_output=True, timeout=600).returncode == 0
        # with Navidrome the id is opaque and unique (and the same name as its own copies, so existing ones are reused); a path can hold characters a file name cannot, so add a hash
        name = f'{_tc_name(ident)}-{rate}.mp3' if conf else f'{_tc_name(ident)[:80]}-{hashlib.md5(ident.encode()).hexdigest()[:8]}-{rate}.mp3'
        got = _cached(_TC_DIR / name, make_local)
        if got is not None or not conf:
            return got
    if not conf:
        return None

    def make(tmp):
        up = _upstream(conf, ident, rate)
        if up is None:
            return False
        _save(up, tmp)
        return True
    return _cached(_TC_DIR / f'{_tc_name(ident)}-{rate}.mp3', make)


# Songs that are slow to start. An .m4a normally has its index (the "moov" box) at the END of the file, so a browser reads the start, finds nothing to play, asks
# for the end, then goes back: three round trips before the first sound. And a song with its cover picture inside it (m4a and opus files from the usual
# downloaders) makes the browser read the whole picture before it will start: 4 seconds on a slow connection for a song that starts in 0.4 s without it.
# So these get a copy with the audio only (no re-encoding, nothing is lost; the cover shown in the app comes from Navidrome, not from the file) and, for an
# m4a, the index first. It is made once, kept with the converted songs, and made ahead for the next songs while the current one plays.
_MP4_EXTS = ('m4a', 'mp4', 'm4b')
_OGG_EXTS = ('opus', 'ogg', 'oga')
_fs_known = {}                                             # id -> True once a song is known to start fine as it is, so it is not looked at again


def _moov_first(head):
    """True if the index comes before the audio in the first bytes of an mp4 file, False if the audio comes first, None if it cannot be told."""
    pos = 0
    while pos + 8 <= len(head):
        size = int.from_bytes(head[pos:pos + 4], 'big')
        kind = head[pos + 4:pos + 8]
        if kind == b'moov':
            return True
        if kind == b'mdat':
            return False
        if size == 1 and pos + 16 <= len(head):
            size = int.from_bytes(head[pos + 8:pos + 16], 'big')
        if size < 8:
            return None
        pos += size
    return None


def _slow_to_start(ext, head):
    """Whether a song, judged by the start of its file, would be slow to start: an mp4 whose index is at the end or that carries a cover picture,
    or an ogg/opus with a cover picture in its tags."""
    if ext in _MP4_EXTS:
        return _moov_first(head[:4096]) is False or b'covr' in head
    return b'METADATA_BLOCK_PICTURE' in head or b'COVERART' in head


_FS_MAX = 120 * 1024 * 1024                                # a longer file (an audiobook) is played as it is: copying it first would make the first request wait


def _size_of(headers):
    total = headers.get('Content-Range', '').rsplit('/', 1)[-1] or headers.get('Content-Length', '')
    return int(total) if total.isdigit() else 0


def _faststart(ident):
    """Path of a quick-starting copy of this song (see above), made now if needed. None when the song starts fine as it is or the copy could not be made."""
    conf = _nd_conf()
    if _fs_known.get(ident):
        return None
    local = _local_src(ident)                              # the file is here: look at and copy it directly
    if not conf and not local:
        return None
    sx = (local.suffix.lstrip('.').lower() if local else next((x['sx'] for x in _library_data().get('tracks', []) if x['f'] == ident), ''))
    if sx not in _MP4_EXTS and sx not in _OGG_EXTS or not shutil.which('ffmpeg'):
        _fs_known[ident] = True
        return None
    mp4 = sx in _MP4_EXTS

    def make(out):
        if local:
            with open(local, 'rb') as fh:
                head = fh.read(1 << 20)
            size = local.stat().st_size
        else:
            probe = _upstream(conf, ident, headers={'Range': 'bytes=0-1048575'})       # the first megabyte tells whether the copy is needed
            if probe is None:
                return False
            head = b''.join(itertools.islice(probe.iter_content(1 << 16), 16))        # (at most 1 MB, even if the server ignores the Range)
            size = _size_of(probe.headers)
            probe.close()
        if not _slow_to_start(sx, head) or size > _FS_MAX:
            _fs_known[ident] = True
            return False
        raw = None
        try:
            if local:
                src = local
            else:
                up = _upstream(conf, ident)
                if up is None:
                    return False
                raw = src = out.with_name(out.name + '.raw')
                _save(up, raw)
            cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-map', '0:a', '-c', 'copy'] + (['-movflags', '+faststart', '-f', 'mp4'] if mp4 else ['-f', 'ogg']) + [str(out)]
            return subprocess.run(cmd, capture_output=True, timeout=120).returncode == 0
        finally:
            if raw is not None:
                try:
                    raw.unlink()
                except OSError:
                    pass
    name = _tc_name(ident)[:80] + ('' if conf else '-' + hashlib.md5(ident.encode()).hexdigest()[:8])      # (the same name as before with Navidrome, so copies already made are reused)
    return _cached(_TC_DIR / ('fs-' + name + ('.m4a' if mp4 else '.ogg')), make)


def _send_cached(f, mimetype):
    resp = send_file(str(f), mimetype=mimetype, conditional=True)
    resp.headers['Cache-Control'] = 'private, max-age=3600'
    return resp


@bp.route('/api/music/prewarm', methods=['POST'])
def music_prewarm():
    """Convert a song in the background (the player asks for the next one while the current one plays)."""
    d = request.get_json(silent=True) or {}
    ident, rate = d.get('id'), d.get('q')
    if _bad_id(ident) or (rate not in TRANSCODE_RATES and rate != 0):
        return jsonify({'error': 'bad request'}), 400
    key = (ident, rate)
    with _bg_lock:
        if key in _bg_pending or len(_bg_pending) >= 2:        # already on its way, or two are waiting: the player asks again at the next song
            return jsonify({'ok': True}), 202
        _bg_pending.add(key)

    def job():
        try:
            with _bg_slot:                                      # one background job at a time, so a song you press play on always has a free slot
                _transcoded(ident, rate) if rate else _faststart(ident)
        finally:
            with _bg_lock:
                _bg_pending.discard(key)
    threading.Thread(target=job, daemon=True).start()
    return jsonify({'ok': True}), 202


@bp.route('/api/music/stream/<path:ident>')
def music_stream(ident):
    if _bad_id(ident):
        return jsonify({'error': 'bad id'}), 400
    conf = _nd_conf()
    local = _local_src(ident)
    if local is not None or not conf:
        # The file is on this machine: serve it from the disk (the original, a converted copy, or a quick-starting copy). Navidrome, if there is one,
        # only supplies the library; the audio does not pass through it.
        fb = bool(request.args.get('fb'))
        rate = 320 if fb else request.args.get('q', type=int)
        if rate in TRANSCODE_RATES:
            f = _transcoded(ident, rate)
            if f is not None:
                resp = _send_cached(f, 'audio/mpeg')
                resp.headers['X-Reclmr-Served'] = f'mp3-{rate}'     # lets the player's quality badge say what it really got
                resp.headers['X-Reclmr-Via'] = 'file'
                return resp
        if not (fb and conf and local is not None):                # (a failed fallback conversion with Navidrome around: let Navidrome try, below)
            fs = _faststart(ident)                                 # a song that is slow to start (see above): the quick-starting copy
            if fs is not None:
                resp = _send_cached(fs, 'audio/ogg' if fs.suffix == '.ogg' else 'audio/mp4')
                resp.headers['X-Reclmr-Via'] = 'file'
                return resp
            if local is not None:
                rel = _nd_paths.get(ident) if conf else ident
                resp = _file_stream(rel)
                resp.headers['X-Reclmr-Via'] = 'file'
                return resp
            return _file_stream(ident)
    # Navidrome has the song but the file is not here: proxy its bytes as before
    if request.args.get('fb'):  # browser could not decode the original: transcode (no seeking)
        return _nd_proxy('stream', {'id': ident, 'format': 'mp3', 'maxBitRate': 320}, ctype='audio/mpeg')
    rate = request.args.get('q', type=int)
    if rate in TRANSCODE_RATES:                        # a lower quality was asked for: a cached MP3, so seeking still works
        f = _transcoded(ident, rate)
        if f is not None:
            resp = _send_cached(f, 'audio/mpeg')
            resp.headers['X-Reclmr-Served'] = f'mp3-{rate}'
            return resp
    fs = _faststart(ident)
    if fs is not None:
        return _send_cached(fs, 'audio/ogg' if fs.suffix == '.ogg' else 'audio/mp4')
    # Navidrome labels WAV audio/x-wav; browsers only reliably accept audio/wav
    ctype = 'audio/wav' if request.args.get('x') == 'wav' else None
    return _nd_proxy('stream', {'id': ident, 'format': 'raw'}, ctype=ctype, cache='private, max-age=3600')      # cacheable, so the first bytes fetched ahead of a skip are still there when the song starts


@bp.after_request
def _served_header(resp):
    """A converted copy says so (see music_stream); everything else the player gets is the file itself."""
    if request.endpoint == 'music.music_stream' and 'X-Reclmr-Served' not in resp.headers:
        resp.headers['X-Reclmr-Served'] = 'mp3-320' if request.args.get('fb') and resp.mimetype == 'audio/mpeg' else 'original'
        resp.headers.setdefault('X-Reclmr-Via', 'navidrome' if _nd_conf() else 'file')
    return resp


_artist_cache = {}


def _plain(text):
    """Navidrome's biography is HTML (a 'Read more on Last.fm' link, entities): reduce it to plain text."""
    import html as _html, re as _re
    t = _re.sub(r'<[^>]+>', ' ', _html.unescape(text or ''))
    t = _re.sub(r'\s*Read more on Last\.fm\.?\s*$', '', _re.sub(r'\s+', ' ', t).strip())
    return t


@bp.route('/api/music/artist/<aid>')
def music_artist_info(aid):
    """About text and similar artists for the artist page. Images come from /api/music/artwork/ar-<id>."""
    if _bad_id(aid):
        return jsonify({'error': 'bad id'}), 400
    if not _nd_conf():
        return jsonify({'bio': '', 'similar': []})
    now = time.time()
    hit = _artist_cache.get(aid)
    if hit and now - hit[0] < 3600:
        return jsonify(hit[1])
    try:
        info = _nd_get('getArtistInfo2', id=aid, count=12).get('artistInfo2', {}) or {}
    except Exception as e:
        return jsonify({'error': str(e)}), 502
    out = {'bio': _plain(info.get('biography', ''))[:2500],
           'similar': [{'id': x['id'], 'name': x.get('name', '')} for x in (info.get('similarArtist') or []) if x.get('id')][:12]}
    if len(_artist_cache) > 500:
        _artist_cache.clear()
    _artist_cache[aid] = (now, out)
    return jsonify(out)


# Navidrome serves a generic stand-in picture for an artist it found no photo for: the same few bytes for every such artist. At 48 px they are
# these two (95 and 14 of the artists in one library). Treating them as "no photo" lets the page fall back to the album cover instead of showing a generic image.
_AR_PLACEHOLDER = {'fcec14e686ad5159a8ed7c51936116d7', '00b7856aa138fc3996c344801c56ed3b'} | {
    h.strip().lower() for h in os.environ.get('RECLMR_PLACEHOLDER_ARTIST_MD5', '').split(',') if h.strip()}
_ar_photo = {}


def _artist_has_photo(aid):
    if aid in _ar_photo:
        return _ar_photo[aid]
    conf = _nd_conf()
    ok = True
    try:
        r = requests.get(f'{conf[0]}/rest/getCoverArt.view', params=_nd_params(conf, {'id': 'ar-' + aid, 'size': 48}), timeout=(5, 20))
        ok = r.status_code == 200 and 'image' in r.headers.get('Content-Type', '') and hashlib.md5(r.content).hexdigest() not in _AR_PLACEHOLDER
    except requests.RequestException:
        return True                                       # could not tell: show what Navidrome has, and do not remember the guess
    if len(_ar_photo) > 3000:
        _ar_photo.clear()
    _ar_photo[aid] = ok
    return ok


_art_slots = threading.BoundedSemaphore(6)          # a grid asks for dozens of covers at once; more than a few at a time only slows the song that is playing


@bp.route('/api/music/diag', methods=['POST'])
def music_diag():
    """The player reports stalls and slow starts, so they can be read in the journal (the phone's own log is out of reach)."""
    b = request.get_json(silent=True) or {}
    dev = str(b.get('dev') or '')[:30]
    for e in (b.get('events') or [])[:30]:
        if isinstance(e, dict):
            print('[player] %s %s' % (dev, ' '.join('%s=%s' % (str(k)[:12], str(v)[:60]) for k, v in list(e.items())[:12])), flush=True)
    return jsonify({'ok': True})


@bp.route('/api/music/artwork/<path:ident>')
@limiter.exempt
def music_artwork(ident):
    if _nd_conf():
        if _bad_id(ident):
            return jsonify({'error': 'bad id'}), 400
        if ident.startswith('ar-'):
            own = _artist_art_file(ident[3:].split('_')[0], 'banner' if request.args.get('banner') else 'avatar')
            if own:
                size = min(1200, max(48, request.args.get('size', 300, type=int)))
                resp = send_file(str(_art_thumb(own, size)), mimetype='image/jpeg', conditional=True)
                resp.headers['Cache-Control'] = 'private, no-cache'
                return resp
        if ident.startswith('pl-'):                          # a playlist with a picture of its own
            own = _artist_art_file('pl_' + ident[3:].split('_')[0], 'avatar')
            if own:
                size = min(1200, max(48, request.args.get('size', 300, type=int)))
                resp = send_file(str(_art_thumb(own, size)), mimetype='image/jpeg', conditional=True)
                resp.headers['Cache-Control'] = 'private, no-cache'
                return resp
        if ident.startswith('ar-') and not _artist_has_photo(ident[3:].split('_')[0]):
            resp = jsonify({'error': 'no photo'})
            resp.status_code = 404
            resp.headers['Cache-Control'] = 'private, max-age=3600'
            return resp
        size = min(1200, max(48, request.args.get('size', 300, type=int)))
        with _art_slots:
            return _nd_proxy('getCoverArt', {'id': ident, 'size': size}, cache='private, max-age=300' if ident.startswith('ar-') else 'private, max-age=86400')
    if ident.startswith('pl-'):                              # a playlist's own picture (no Navidrome: nothing else to fall back to)
        own = _artist_art_file('pl_' + ident[3:].split('_')[0], 'avatar')
        if own:
            size = min(1200, max(48, request.args.get('size', 300, type=int)))
            resp = send_file(str(_art_thumb(own, size)), mimetype='image/jpeg', conditional=True)
            resp.headers['Cache-Control'] = 'private, no-cache'
            return resp
        return jsonify({'error': 'no picture'}), 404
    return _file_artwork(ident)


# ─── Artist photo / banner from SoundCloud (for artists Navidrome finds nothing for) ───
# You pick the right profile (search results or a pasted link); only that profile's avatar and banner are downloaded and kept in artist_art/.
# SoundCloud has no public API: profile pages carry their data in the HTML, and search needs the public client_id its own web player uses.
_ART_DIR = _APP_DIR / 'artist_art'
_SPOTIFY_IMG = ('.scdn.co', '.spotifycdn.com')          # where Spotify keeps its pictures (playlists made by people are on the second)
_SC_UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0'}
_sc_cid = {'v': None}


def _artist_art_file(aid, kind):
    aid = re.sub(r'[^A-Za-z0-9_-]', '_', aid or '')
    for k in ([kind, 'avatar'] if kind == 'banner' else [kind]):
        f = _ART_DIR / f'{aid}-{k}.jpg'
        if f.exists():
            return f
    return None


def _art_thumb(src, size):
    """The saved picture scaled down to `size` px (cached next to it), so list pages do not download full-size photos."""
    size = (size + 99) // 100 * 100                      # a few steps, so the cache stays small
    try:
        from PIL import Image
        out = _ART_DIR / '.thumbs' / f'{src.stem}-{size}-{int(src.stat().st_mtime)}.jpg'
        if not out.exists():
            im = Image.open(src)
            if max(im.size) <= size:
                return src
            out.parent.mkdir(exist_ok=True)
            for old in out.parent.glob(f'{src.stem}-*.jpg'):
                old.unlink(missing_ok=True)
            im.convert('RGB').resize((round(im.width * size / max(im.size)), round(im.height * size / max(im.size))), Image.LANCZOS).save(out, 'JPEG', quality=84)
        return out
    except Exception:
        return src


def _sc_client_id(refresh=False):
    if _sc_cid['v'] and not refresh:
        return _sc_cid['v']
    html = requests.get('https://soundcloud.com/', headers=_SC_UA, timeout=15).text
    for u in reversed(re.findall(r'https://a-v2\.sndcdn\.com/assets/[^"\']+\.js', html)):
        m = re.search(r'client_id:"([A-Za-z0-9]{32})"', requests.get(u, headers=_SC_UA, timeout=20).text)
        if m:
            _sc_cid['v'] = m.group(1)
            return m.group(1)
    raise RuntimeError('SoundCloud client id not found')


@bp.route('/api/music/sc/search')
def music_sc_search():
    q = (request.args.get('q') or '').strip()[:100]
    if not q:
        return jsonify([])
    for attempt in (0, 1):
        try:
            r = requests.get('https://api-v2.soundcloud.com/search/users', headers=_SC_UA, timeout=15,
                             params={'q': q, 'limit': 8, 'client_id': _sc_client_id(attempt == 1)})
            if r.status_code in (401, 403) and attempt == 0:
                continue
            r.raise_for_status()
            break
        except (requests.RequestException, RuntimeError) as e:
            if attempt == 1:
                return jsonify({'error': 'SoundCloud lookup failed: ' + str(e)[:120]}), 502
    return jsonify([{'name': u.get('username', ''), 'permalink': u.get('permalink', ''), 'followers': u.get('followers_count', 0),
                     'tracks': u.get('track_count', 0), 'avatar': u.get('avatar_url', '')}
                    for u in r.json().get('collection', []) if u.get('permalink')])


def _sc_fetch_image(url, hosts=('.sndcdn.com',)):
    from urllib.parse import urlparse
    from PIL import Image
    import io
    host = urlparse(url).hostname or ''
    if not (url.startswith('https://') and host.endswith(hosts)):
        raise ValueError('unexpected image host')
    r = requests.get(url, headers=_SC_UA, timeout=20, stream=True)
    r.raise_for_status()
    data = r.raw.read(12 * 1024 * 1024 + 1, decode_content=True)
    if len(data) > 12 * 1024 * 1024:
        raise ValueError('image too large')
    im = Image.open(io.BytesIO(data)).convert('RGB')
    out = io.BytesIO()
    im.save(out, 'JPEG', quality=88)
    return out.getvalue()


def _sc_import(aid, permalink):
    """Download a profile's avatar/banner into artist_art/. Returns (user dict, ['avatar','banner'] that were saved)."""
    html = requests.get(f'https://soundcloud.com/{permalink}', headers=_SC_UA, timeout=20).text
    hy = re.search(r'__sc_hydration = (\[.*?\]);</script>', html, re.S)
    user = next((x['data'] for x in json.loads(hy.group(1)) if x.get('hydratable') == 'user'), None) if hy else None
    if not user:
        raise LookupError(permalink)
    got = []
    _ART_DIR.mkdir(exist_ok=True)
    av = user.get('avatar_url') or ''
    if av and 'default_avatar' not in av:
        (_ART_DIR / f'{aid}-avatar.jpg').write_bytes(_sc_fetch_image(av.replace('-large.', '-t500x500.')))
        got.append('avatar')
    vis = user.get('visual_url') or ''
    if vis:
        (_ART_DIR / f'{aid}-banner.jpg').write_bytes(_sc_fetch_image(vis))
        got.append('banner')
    return user, got


@bp.route('/api/music/sc/apply', methods=['POST'])
def music_sc_apply():
    d = request.get_json(silent=True) or {}
    aid = re.sub(r'[^A-Za-z0-9_-]', '_', str(d.get('aid') or ''))
    ref = str(d.get('profile') or '').strip()
    m = re.match(r'^(?:https?://(?:www\.|m\.)?soundcloud\.com/)?([A-Za-z0-9_-]{2,60})/?(?:[?#].*)?$', ref)
    if not aid or not m:
        return jsonify({'error': 'Give a soundcloud.com profile link'}), 400
    try:
        user, got = _sc_import(aid, m.group(1))
    except LookupError:
        return jsonify({'error': 'Profile not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Import failed: ' + str(e)[:120]}), 502
    if not got:
        return jsonify({'error': (user.get('username') or 'That profile') + ' has no photo or banner'}), 404
    return jsonify({'ok': True, 'name': user.get('username', ''), 'got': got})


def _spotify_page(sid, kind='artist'):
    """Public artist (or playlist) page: name, photo (og:image) and, for an artist, the wide header image if it has one."""
    html = requests.get(f'https://open.spotify.com/{kind}/{sid}', headers={'User-Agent': 'Mozilla/5.0'}, timeout=20).text   # a browser-like UA gets a page without the preview tags
    img = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    nm = re.search(r'<meta property="og:title" content="([^"]*)"', html)
    ds = re.search(r'<meta property="og:description" content="([^"]*)"', html)
    hdr = re.search(r'https://i\.scdn\.co/image/ab6742d30000(?:52|53)b7([0-9a-f]+)', html)
    import html as _h
    return {'name': _h.unescape(nm.group(1)) if nm else '', 'avatar': img.group(1) if img else '',
            'info': _h.unescape(ds.group(1)) if ds else '',
            'banner': ('https://i.scdn.co/image/ab6742d3000053b7' + hdr.group(1)) if hdr else ''}


def _web_spotify_ids(q):
    """open.spotify.com artist ids found by web-searching `q` (Yahoo, then Bing; neither needs a key). Up to 5, best-ranked first."""
    import base64, urllib.parse
    ua = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0', 'Accept-Language': 'en'}
    term = q + ' spotify artist site:open.spotify.com'
    found = []
    for url, param in (('https://search.yahoo.com/search', 'p'), ('https://www.bing.com/search', 'q')):
        try:
            html = requests.get(url, params={param: term}, headers=ua, timeout=20).text.replace('&amp;', '&')
        except requests.RequestException:
            continue
        text = urllib.parse.unquote(html)
        for b in re.findall(r'[?&]u=a1([A-Za-z0-9_-]+)', html):          # Bing wraps result links in base64
            try:
                text += ' ' + base64.urlsafe_b64decode(b + '=' * (-len(b) % 4)).decode('utf8', 'ignore')
            except ValueError:
                pass
        for sid in re.findall(r'open\.spotify\.com/(?:intl-[a-z]+/)?artist/([A-Za-z0-9]{22})', text):
            if sid not in found:
                found.append(sid)
        if len(found) >= 3:
            break
    return found[:5]


@bp.route('/api/music/art/spotify/search')
def music_spotify_search():
    """Find Spotify artist pages for a name via a web search (Spotify's own search needs an API key), then read each public page."""
    q = (request.args.get('q') or '').strip()[:100]
    if not q:
        return jsonify([])
    ids = _web_spotify_ids(q)
    if not ids:
        return jsonify({'error': 'The web search found no Spotify page. Try again, or paste the artist link.'}), 502
    from concurrent.futures import ThreadPoolExecutor

    def one(sid):
        try:
            p = _spotify_page(sid)
            return {'id': sid, 'name': p['name'], 'info': p['info'], 'avatar': p['avatar'], 'banner': bool(p['banner'])}
        except Exception:
            return None
    with ThreadPoolExecutor(5) as ex:
        out = [x for x in ex.map(one, ids) if x and x['name']]
    low = q.lower()
    out.sort(key=lambda x: x['name'].lower() != low)       # exact name first, the search engine's order otherwise
    return jsonify(out)


@bp.route('/api/music/art/deezer/search')
def music_deezer_search():
    """Deezer's public artist search (no key): finds photos for many small artists."""
    q = (request.args.get('q') or '').strip()[:100]
    if not q:
        return jsonify([])
    try:
        r = requests.get('https://api.deezer.com/search/artist', params={'q': q, 'limit': 8}, headers=_SC_UA, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        return jsonify({'error': 'Deezer lookup failed: ' + str(e)[:120]}), 502
    return jsonify([{'id': str(a['id']), 'name': a.get('name', ''), 'fans': a.get('nb_fan', 0), 'avatar': a.get('picture_medium', '')}
                    for a in r.json().get('data', []) if a.get('id')])


@bp.route('/api/music/art/apply', methods=['POST'])
def music_art_apply():
    """Save an artist photo from Deezer (id from the search) or a pasted Spotify artist link (its page's public og:image)."""
    d = request.get_json(silent=True) or {}
    aid = re.sub(r'[^A-Za-z0-9_-]', '_', str(d.get('aid') or ''))
    src, ref = str(d.get('source') or ''), str(d.get('ref') or '').strip()
    banner = False
    if not aid:
        return jsonify({'error': 'bad request'}), 400
    try:
        if src == 'deezer' and re.fullmatch(r'\d{1,12}', ref):
            a = requests.get(f'https://api.deezer.com/artist/{ref}', headers=_SC_UA, timeout=15).json()
            url, name, hosts = a.get('picture_xl') or '', a.get('name', ''), ('.dzcdn.net',)
            if 'images/artist//' in url:
                url = ''
        elif src == 'spotify':
            m = re.search(r'artist[/:]([A-Za-z0-9]{22})', ref) or re.fullmatch(r'()([A-Za-z0-9]{22})', ref)
            sid = m.group(m.lastindex) if m else None
            if not sid:
                return jsonify({'error': 'Give an open.spotify.com/artist/… link'}), 400
            info = _spotify_page(sid)
            url, name, hosts = info['avatar'], info['name'], _SPOTIFY_IMG
            if info['banner']:
                _ART_DIR.mkdir(exist_ok=True)
                (_ART_DIR / f'{aid}-banner.jpg').write_bytes(_sc_fetch_image(info['banner'], hosts))
                banner = True
        else:
            return jsonify({'error': 'bad request'}), 400
        if not url:
            return jsonify({'error': (name or 'That artist') + ' has no photo'}), 404
        _ART_DIR.mkdir(exist_ok=True)
        (_ART_DIR / f'{aid}-avatar.jpg').write_bytes(_sc_fetch_image(url, hosts))
    except Exception as e:
        return jsonify({'error': 'Import failed: ' + str(e)[:120]}), 502
    return jsonify({'ok': True, 'name': name, 'got': ['photo'] + (['banner'] if banner else [])})


@bp.route('/api/music/art/overrides')
def music_art_overrides():
    """Artists with a saved photo/banner: {'v': {artist id: last-changed time}, 'b': [ids that have a real banner]}.
    The app tags picture URLs with the time so a stale cached picture is never shown."""
    v, b = {}, []
    if _ART_DIR.exists():
        for f in _ART_DIR.glob('*-*.jpg'):
            aid, kind = f.name[:-4].rsplit('-', 1)
            v[aid] = max(v.get(aid, 0), int(f.stat().st_mtime))
            if kind == 'banner':
                b.append(aid)
    return jsonify({'v': v, 'b': b})


@bp.route('/api/music/sc/clear', methods=['POST'])
def music_sc_clear():
    aid = re.sub(r'[^A-Za-z0-9_-]', '_', str((request.get_json(silent=True) or {}).get('aid') or ''))
    for k in ('avatar', 'banner'):
        (_ART_DIR / f'{aid}-{k}.jpg').unlink(missing_ok=True)
    return jsonify({'ok': True})


# ─── A playlist's own picture: an uploaded photo, or the picture of a Spotify playlist link. Kept in artist_art/ as pl_<id>-avatar.jpg ───
_PL_COVER_MAX = 12 * 1024 * 1024


def _pl_cover_file(pid):
    return _ART_DIR / (re.sub(r'[^A-Za-z0-9_-]', '_', 'pl_' + pid) + '-avatar.jpg')


def _pl_cover_clear(pid):
    f = _pl_cover_file(pid)
    f.unlink(missing_ok=True)
    for old in (_ART_DIR / '.thumbs').glob(f'{f.stem}-*.jpg'):
        old.unlink(missing_ok=True)


def _square_jpeg(data):
    """A picture as a square JPEG (cut from the middle, at most 1000 px): the shape of every cover in the app. Raises ValueError if it is not a picture."""
    import io
    from PIL import Image, ImageOps
    try:
        im = Image.open(io.BytesIO(data))
        if im.width * im.height > 60_000_000:
            raise ValueError('picture too large')
        im = ImageOps.exif_transpose(im).convert('RGB')
    except (OSError, Image.DecompressionBombError) as e:
        raise ValueError('not a picture') from e
    side = min(im.size)
    im = im.crop(((im.width - side) // 2, (im.height - side) // 2, (im.width + side) // 2, (im.height + side) // 2))
    if side > 1000:
        im = im.resize((1000, 1000), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, 'JPEG', quality=88)
    return out.getvalue()


@bp.route('/api/music/playlist/<pid>/cover', methods=['POST'])
def music_playlist_cover(pid):
    """Give a playlist its own picture: an uploaded `file`, or `link` to an open.spotify.com/playlist page (its public picture is used)."""
    if _bad_id(pid):
        return jsonify({'error': 'bad request'}), 400
    try:
        if _nd_conf():
            _nd_get('getPlaylist', id=pid)                   # only for a playlist that exists
        elif _lp.entries(pid) is None:
            raise LookupError(pid)
    except Exception:
        return jsonify({'error': 'Playlist not found'}), 404
    try:
        up = request.files.get('file')
        if up:
            data = up.read(_PL_COVER_MAX + 1)
            if len(data) > _PL_COVER_MAX:
                return jsonify({'error': 'That picture is too big (12 MB at most)'}), 413
        else:
            ref = str((request.get_json(silent=True) or {}).get('link') or '').strip()
            m = re.search(r'playlist[/:]([A-Za-z0-9]{22})', ref) or re.fullmatch(r'()([A-Za-z0-9]{22})', ref)
            if not m:
                return jsonify({'error': 'Give an open.spotify.com/playlist/… link'}), 400
            info = _spotify_page(m.group(m.lastindex), 'playlist')
            if not info['avatar']:
                return jsonify({'error': 'Spotify shows no picture for that playlist (is it public?)'}), 404
            data = _sc_fetch_image(info['avatar'], _SPOTIFY_IMG)
        jpg = _square_jpeg(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Import failed: ' + str(e)[:120]}), 502
    _ART_DIR.mkdir(exist_ok=True)
    f = _pl_cover_file(pid)
    f.write_bytes(jpg)
    return jsonify({'ok': True, 'v': int(f.stat().st_mtime)})


@bp.route('/api/music/playlist/<pid>/cover/clear', methods=['POST'])
def music_playlist_cover_clear(pid):
    if _bad_id(pid):
        return jsonify({'error': 'bad request'}), 400
    _pl_cover_clear(pid)
    return jsonify({'ok': True})


# ─── Lyrics: from Navidrome (tags / .lrc files) first, then from LRCLIB, a free lyrics site ───
# LRCLIB gets the artist, title, album and length of the song being played; what it returns is cached in lyrics_cache/ so each song is asked once.
_lyr_cache = {}
_LYR_DIR = _APP_DIR / 'lyrics_cache'
_LRC_RE = re.compile(r'^\s*((?:\[\d+:\d+(?:[.:]\d+)?\])+)(.*)$')


def _parse_lrc(text):
    lines = []
    for raw in (text or '').splitlines():
        m = _LRC_RE.match(raw)
        if not m:
            continue
        v = re.sub(r'<\d+:\d+(?:[.:]\d+)?>', '', re.sub(r'^\s*v\d:\s*', '', m.group(2))).strip()
        for mm, ss in re.findall(r'\[(\d+):(\d+(?:[.:]\d+)?)\]', m.group(1)):
            lines.append([int((int(mm) * 60 + float(ss.replace(':', '.'))) * 1000), v])
    lines.sort(key=lambda x: x[0])
    return [l for l in lines if l[1]] or []


_whisper = {}
_whisper_lock = threading.Lock()
_WORD = re.compile(r"\w{3,}", re.U)


def _words(text):
    return set(_WORD.findall((text or '').lower()))


def _pick_by_ear(groups, heard):
    """Which of several different sets of lyrics fits what was heard at the start of the song. groups: [(lines, hit), ...].
    Returns the best index, or None when no set is clearly better than the others."""
    heard = _words(heard)
    if len(heard) < 4:
        return None
    scores = []
    for lines, _ in groups:
        bag = _words(' '.join(x[1] for x in lines if x[0] is not None and x[0] < 80000))
        scores.append(len(heard & bag) / len(heard))
    order = sorted(range(len(groups)), key=lambda i: -scores[i])
    best = order[0]
    if scores[best] < .2 or (len(order) > 1 and scores[best] - scores[order[1]] < .08):
        return None
    return best


def _listen(tid, seconds=75):
    """What is sung in the first stretch of a song, as text (the speech model already used by the voice feature, run on the server). '' if it cannot be done."""
    conf = _nd_conf()
    if not conf:
        return ''
    try:
        import numpy as np
        up = requests.get(f'{conf[0]}/rest/stream.view', params=_nd_params(conf, {'id': tid, 'format': 'mp3', 'maxBitRate': 64}),
                          stream=True, timeout=(5, 30))
        if up.status_code >= 400 or 'json' in up.headers.get('Content-Type', '') or 'xml' in up.headers.get('Content-Type', ''):
            up.close()
            return ''
        buf = b''
        for chunk in up.iter_content(65536):
            buf += chunk
            if len(buf) >= 8000 * seconds + 30000:           # 64 kbit/s is 8000 bytes a second
                break
        up.close()
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-t', str(seconds), '-f', 's16le', '-ac', '1', '-ar', '16000', 'pipe:1'],
                           input=buf, capture_output=True, timeout=40)
        if not r.stdout:
            return ''
        audio = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        with _whisper_lock:                                   # one at a time: it uses the processor hard
            if 'm' not in _whisper:
                from faster_whisper import WhisperModel
                _whisper['m'] = WhisperModel('base', device='cpu', compute_type='int8', local_files_only=True)
            segs, _ = _whisper['m'].transcribe(audio, beam_size=1, vad_filter=False)
            return ' '.join(sg.text for sg in segs)
    except Exception:
        return ''


_NAME_JUNK = re.compile(r'\(.*?\)|\[.*?\]|\b(feat|ft|featuring|with|prod)\b.*|[^\w ]', re.I | re.U)


def _norm_name(s):
    return re.sub(r'\s+', ' ', _NAME_JUNK.sub(' ', (s or '').lower())).strip()


def _like(a, b, cut):
    """Whether two song or artist names are the same thing written a little differently (case, punctuation, (feat. ...), a trailing word)."""
    a, b = _norm_name(a), _norm_name(b)
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 4 and (a in b or b in a)) or difflib.SequenceMatcher(None, a, b).ratio() >= cut


def _same_song(h, title, artists, dur):
    """A search hit counts only if its title and artist match the song being played. Entries filed under an original-script name
    (the sung language) cannot be compared with an English tag, so those pass on an almost exact length instead."""
    t, a = h.get('trackName') or '', h.get('artistName') or ''
    if _like(t, title, .72) and any(_like(a, x, .7) for x in artists):
        return True
    if re.search(r'[\u0400-\u04ff\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af\u0900-\u097f\u0a00-\u0a7f]', t + a):
        return abs((h.get('duration') or 0) - dur) <= 2
    return False


def _lrclib(title, artist, album, dur, artists=None, tid=None):
    """Best match from lrclib.net: synced lyrics if it has them, else plain ones. [] when nothing fits.
    Songs tagged with an English title often have both the sung lyrics and an English translation on the site (same times, same length);
    when a result carries an original-script title (スローモーションリプレイ), the sung-language lyrics win over the translation."""
    hdr = {'User-Agent': 'reclmr (self-hosted music player)'}
    artists = artists or [artist]
    hits, ok = [], False
    for url, params in (('https://lrclib.net/api/get', {'track_name': title, 'artist_name': artist, 'album_name': album, 'duration': int(dur)}),
                        ('https://lrclib.net/api/search', {'track_name': title, 'artist_name': artist}),
                        ('https://lrclib.net/api/search', {'q': artist + ' ' + title})):          # the free-text search also finds entries filed under the original-script title
        try:
            r = requests.get(url, params=params, headers=hdr, timeout=8)
            if r.status_code >= 500:                          # the site is busy: wait a moment and ask once more
                time.sleep(1.2)
                r = requests.get(url, params=params, headers=hdr, timeout=8)
        except requests.RequestException:
            continue
        if r.status_code in (200, 404):                       # a real answer (an overloaded site is not "no lyrics")
            ok = True
        if r.status_code == 200:
            try:
                j = r.json()
            except ValueError:
                continue
            hits += j if isinstance(j, list) else [j]
    if not ok:
        return None                                           # could not ask: do not remember an empty answer
    hits = [h for h in hits if abs((h.get('duration') or 0) - dur) <= 4]
    hits = [h for h in hits if _same_song(h, title, artists, dur)]      # the site's search is loose: a song of about the same length is not necessarily this song
    if any(h.get('instrumental') for h in hits) and not any(h.get('syncedLyrics') or h.get('plainLyrics') for h in hits):
        return []
    nonlatin = re.compile(r'[\u0400-\u04ff\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af\u0900-\u097f\u0a00-\u0a7f]')

    def share(txt):
        return len(nonlatin.findall(txt)) / max(1, len(re.sub(r'\W', '', txt)))
    sung_original = any(nonlatin.search(h.get('trackName') or '') for h in hits)         # a non-Latin title exists, so the song's own language is not Latin script
    cands = [(h, _parse_lrc(h.get('syncedLyrics'))) for h in hits]
    cands = [(h, ln) for h, ln in cands if ln]
    if sung_original:
        orig = [(h, ln) for h, ln in cands if share(' '.join(x[1] for x in ln)) >= 0.3]
        cands = orig or cands
    if cands:
        close = [c for c in cands if abs((c[0].get('duration') or 0) - dur) <= min(abs((x[0].get('duration') or 0) - dur) for x in cands) + 1.5]
        distinct = {}
        for h, ln in close:                                    # versions of one song carry different lyrics (an alternate take, a mislabelled upload): tell them apart by their first lines
            distinct.setdefault(' '.join(re.sub(r'\W', '', x[1].lower()) for x in ln[:5]), (ln, h))
        if tid and len(distinct) > 1:
            groups = list(distinct.values())
            i = _pick_by_ear(groups, _listen(tid))
            if i is not None:
                return {'synced': True, 'lines': groups[i][0]}
        h, ln = min(cands, key=lambda c: abs((c[0].get('duration') or 0) - dur))
        return {'synced': True, 'lines': ln}
    for h in hits:
        plain = [[None, x.strip()] for x in (h.get('plainLyrics') or '').splitlines()]
        if any(x[1] for x in plain):
            return {'synced': False, 'lines': plain}
    return []


_JP_KANA = re.compile(r'[\u3040-\u30ff]')
_JP_ANY = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')
_jp = {}


def _romaji_lines(lines):
    """Japanese lyrics as Hepburn romaji (janome splits the words, pykakasi spells them). Only songs with kana in them: a Chinese song stays as written.
    Each line becomes [start, romaji, original]. Returns the lines unchanged when the libraries are missing."""
    if not any(l[1] and _JP_KANA.search(l[1]) for l in lines):
        return lines
    try:
        if 'tk' not in _jp:
            from janome.tokenizer import Tokenizer
            import pykakasi
            _jp['tk'], _jp['kk'] = Tokenizer(), pykakasi.kakasi()
        tk, kk = _jp['tk'], _jp['kk']
    except Exception:
        return lines
    out = []
    for start, text in lines:
        if not text or not _JP_ANY.search(text):
            out.append([start, text])
            continue
        groups = []                                           # [kana or plain text, is Japanese]; verb endings stay glued to their verb: hoshikatta, not hoshikatsu ta
        for tok in tk.tokenize(text):
            if not _JP_ANY.search(tok.surface):
                groups.append([tok.surface, False])
                continue
            rd = tok.phonetic if tok.phonetic not in ('*', '') else tok.reading
            kana = rd if rd and rd != '*' else tok.surface
            pos = tok.part_of_speech.split(',')
            if groups and groups[-1][1] and (pos[0] == '助動詞' or (pos[0] == '動詞' and pos[1] in ('接尾', '非自立'))):
                groups[-1][0] += kana
            else:
                groups.append([kana, True])
        words = [''.join(x['hepburn'] for x in kk.convert(g)) if jp else g for g, jp in groups]
        rom = re.sub(r'\s+', ' ', ' '.join(words)).strip()
        rom = re.sub(r'\s+([,.!?)\u3001\u3002\uff01\uff1f])', r'\1', rom)
        out.append([start, rom[:1].upper() + rom[1:], text])
    return out


_LRC_TIME = re.compile(r'\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]')


def _read_lrc(song):
    """{synced, lines} from the .lrc file beside a song, or None. Timed lines ([01:23.45] words) make it synced; plain text is shown untimed."""
    if not song:
        return None
    f = song.with_suffix('.lrc')
    try:
        if not f.is_file() or f.stat().st_size > 512 * 1024:
            return None
        text = f.read_text(encoding='utf-8-sig', errors='replace')
    except OSError:
        return None
    timed, plain = [], []
    for raw in text.splitlines():
        stamps = list(_LRC_TIME.finditer(raw))
        words = _LRC_TIME.sub('', raw).strip()
        if stamps:
            for m in stamps:
                frac = (m.group(3) or '0')
                timed.append([int(m.group(1)) * 60000 + int(m.group(2)) * 1000 + int(frac.ljust(3, '0')[:3]), re.sub(r'<\d+:\d+(?:[.:]\d+)?>', '', words).strip()])
        elif raw.strip() and not re.match(r'^\[[a-zA-Z]+:.*\]$', raw.strip()):          # [ar:..] [ti:..] header tags are not lyrics
            plain.append([None, raw.strip()])
    if timed:
        return {'synced': True, 'lines': sorted((l for l in timed if l[1]), key=lambda l: l[0])}
    return {'synced': False, 'lines': plain} if plain else None


@bp.route('/api/music/lyrics/<path:tid>')
def music_lyrics(tid):
    """{synced, lines: [[start ms or null, text], ...]} for a song; empty when none can be found."""
    if _bad_id(tid):
        return jsonify({'error': 'bad id'}), 400
    hit = _lyr_cache.get(tid)
    if hit and time.time() - hit[0] < 3600:
        return jsonify(hit[1])
    out = {'synced': False, 'lines': []}
    if _nd_conf():
        try:
            lst = (_nd_get('getLyricsBySongId', id=tid).get('lyricsList') or {}).get('structuredLyrics') or []
            best = next((x for x in lst if x.get('synced')), lst[0] if lst else None)
            if best:
                off = int(best.get('offset') or 0)
                synced = bool(best.get('synced'))
                for l in best.get('line') or []:
                    v = re.sub(r'<\d+:\d+(?:[.:]\d+)?>', '', re.sub(r'^\s*v\d:\s*', '', str(l.get('value') or ''))).strip()      # "v1:" is a singer tag, <00:01.2> a per-word time; some lyric files carry both
                    if synced and not v:
                        continue
                    out['lines'].append([max(0, int(l.get('start') or 0) + off) if synced else None, v])
                out['synced'] = synced and bool(out['lines'])
        except Exception:
            return jsonify(out)                             # Navidrome hiccup: not cached, try again next time
    else:                                                   # no Navidrome: a .lrc file next to the song (Artist - Title.lrc)
        out = _read_lrc(_safe_music_path(tid)) or out
    if not out['synced']:                                   # nothing timed in the files: ask LRCLIB (once per song)
        f = _LYR_DIR / (re.sub(r'[^A-Za-z0-9_-]', '_', tid) + '.json')
        got = None
        try:
            c = json.loads(f.read_text())
            if c.get('v') == 4 and (c.get('lines') or time.time() - c.get('at', 0) < 7 * 86400):
                got = {'synced': c.get('synced', False), 'lines': c.get('lines', [])}
        except (OSError, ValueError):
            pass
        if got is None:
            t = next((x for x in _library_data().get('tracks', []) if x['f'] == tid), None)
            if t and t.get('d'):
                artist = (t.get('as') or [[0, t.get('ar', '')]])[0][1]
                res = _lrclib(t['t'], artist, t.get('al', ''), t['d'], [x[1] for x in (t.get('as') or [])] or [t.get('ar', '')], tid)
                if res is None:
                    return jsonify(out)
                got = res if res else {'synced': False, 'lines': []}
                try:
                    _LYR_DIR.mkdir(exist_ok=True)
                    f.write_text(json.dumps({'v': 4, 'at': time.time(), **got}, ensure_ascii=False))
                except OSError:
                    pass
        if got and got['lines'] and (got['synced'] or not out['lines']):
            out = got
    if out['lines']:
        out = {**out, 'lines': _romaji_lines(out['lines'])}
    if out['lines']:                                        # (no lyrics yet is not remembered: a .lrc file added later shows up at once; LRCLIB's own "none" answer is kept on disk above)
        if len(_lyr_cache) > 400:
            _lyr_cache.clear()
        _lyr_cache[tid] = (time.time(), out)
    return jsonify(out)


# ─── Cross-device "now playing" session ──────────────────────────────────
# One shared session (queue, position, mode flags) so another device can resume
# where this one stopped. `updated` comes from the server clock, so devices with
# skewed clocks can't make stale state win. Position-only updates omit the queue.
_SESSION_FILE = _APP_DIR / 'music_session.json'
_session_lock = threading.Lock()


def _load_session():
    try:
        return json.loads(_SESSION_FILE.read_text())
    except Exception:
        return None


@bp.route('/api/music/session', methods=['GET'])
def music_session_get():
    with _session_lock:
        data = _load_session()
    return jsonify({'session': data, 'now': time.time(), 'active': _effective_active(data)})


class _Bad(Exception):
    pass


_GONE_GRACE = 8.0           # seconds a dropped device keeps its role (covers a page refresh)
_ACTIVE_IDLE = 300          # a paused device stays "active" this long, then playback is free to move
_conns = {}                 # device id -> {'ws', 'label', 'lock'}
_conn_lock = threading.RLock()
_gone = {}                  # device id -> Timer (grace period before a dropped device counts as stopped)
_pending = {}               # transfer target -> Timer


def _effective_active(sess):
    """The device that is currently outputting (or recently was), if it is still connected."""
    if not sess:
        return None
    a = sess.get('active')
    if not a or (a not in _conns and a not in _gone):     # a just-dropped device (page refresh) keeps its role briefly
        return None
    st = sess.get('state') or {}
    if not st.get('playing') and time.time() - sess.get('updated', 0) > _ACTIVE_IDLE:
        return None
    return a


def _devices(sess):
    act = _effective_active(sess)
    with _conn_lock:
        items = sorted(((d, c['label']) for d, c in _conns.items() if not c.get('ctl')), key=lambda x: (x[1], x[0]))
    seen, out = {}, []
    for d, label in items:                      # "Chrome on Linux", "Chrome on Linux (2)" ...
        seen[label] = seen.get(label, 0) + 1
        out.append({'id': d, 'label': label if seen[label] == 1 else '%s (%d)' % (label, seen[label]), 'active': d == act})
    return out


def _send(dev, obj):
    with _conn_lock:
        c = _conns.get(dev)
    if not c:
        return False
    try:
        with c['lock']:
            c['ws'].send(json.dumps(obj))
        return True
    except Exception:
        return False


def _state_msg(sess):
    return {'t': 'state', 's': sess, 'devices': _devices(sess), 'active': _effective_active(sess), 'now': time.time()}


def _broadcast(sess=None, skip=None):
    sess = sess if sess is not None else _load_session()
    msg = _state_msg(sess or {})
    with _conn_lock:
        ids = list(_conns)
    for d in ids:
        if d != skip:
            _send(d, msg)


def _validate_report(b):
    try:
        pos = float(b.get('pos', 0))
        qi = int(b.get('qi', 0))
    except (TypeError, ValueError):
        raise _Bad('bad numbers')
    if not (0 <= pos < 1e6) or qi < 0:
        raise _Bad('bad request')
    rp = b.get('rp', 'off')
    if rp not in ('off', 'all', 'one'):
        raise _Bad('bad repeat')
    q = b.get('q')
    if q is not None and (not isinstance(q, list) or not q or len(q) > 2000
                          or any(not isinstance(i, str) or not i or len(i) > 600 for i in q)):
        raise _Bad('bad queue')
    return pos, qi, rp, q


def _clean_ctx(b):
    """The playlist/album/artist a queue was started from: {'k', 'v'} or None."""
    cx = b.get('cx')
    if (isinstance(cx, dict) and cx.get('k') in ('album', 'playlist', 'artist', 'liked')
            and isinstance(cx.get('v'), str) and len(cx['v']) <= 600):
        return {'k': cx['k'], 'v': cx['v']}
    return None


def _report(dev, label, b, force=False):
    """Merge a device's playback report into the shared session.

    Only the active device may update an active session, except that a device which starts
    playing takes over (and the previous one is told to stop). `force` is used for an
    explicit handoff, where the sender is still the active device anyway."""
    pos, qi, rp, q = _validate_report(b)
    stop = None
    with _session_lock:
        cur = _load_session() or {}
        act = _effective_active(cur)
        playing = bool(b.get('playing'))
        if act and act != dev and not playing and not force:
            return {'ok': True, 'ignored': True}        # a non-active device must not clobber the session
        st = dict(cur.get('state') or {})
        if q is not None:
            st['q'] = q
        queue = st.get('q') or []
        if qi >= len(queue):
            return {'ok': False, 'stale': True}
        if q is None and queue[qi] != b.get('cur'):
            return {'ok': False, 'stale': True}
        st.update(qi=qi, pos=round(pos, 1), playing=playing, sh=bool(b.get('sh')), rp=rp)
        if 'cx' in b:
            st['cx'] = _clean_ctx(b)
        if act == dev or playing:
            new_active = dev
        else:
            new_active = None                            # idle report with nobody active: store, but don't claim
        if playing and act and act != dev:
            stop = act
        out = {'state': st, 'updated': time.time(), 'dev': dev, 'label': label, 'active': new_active}
        try:
            tmp = _SESSION_FILE.with_suffix('.tmp')
            tmp.write_text(json.dumps(out))
            tmp.replace(_SESSION_FILE)
        except OSError:
            raise _Bad('could not save')
    if stop:
        _send(stop, {'t': 'cmd', 'a': 'stop', 'from': dev})
    _broadcast(out, skip=dev)
    return {'ok': True, 'updated': out['updated']}


@bp.route('/api/music/session', methods=['POST'])
def music_session_set():
    b = request.get_json(silent=True) or {}
    dev = str(b.get('dev') or '')[:60]
    if not dev:
        return jsonify({'error': 'bad request'}), 400
    try:
        return jsonify(_report(dev, str(b.get('label') or '')[:60], b))
    except _Bad as e:
        return jsonify({'error': str(e)}), 400


# ─── live "Connect" channel (WebSocket) ──────────────────────────────────
# Devices stay connected; the active one reports playback, the others become remotes whose
# commands are forwarded to it. A transfer first asks the old device for its exact position.
def _extrapolated(sess):
    st = dict(sess.get('state') or {})
    if st.get('playing'):
        st['pos'] = round(st.get('pos', 0) + max(0, time.time() - sess.get('updated', time.time())), 1)
    return st


def _finalize_transfer(target):
    t = _pending.pop(target, None)
    if t:
        t.cancel()
    with _session_lock:
        cur = _load_session()
        if not cur or target not in _conns:
            return
        st = _extrapolated(cur) if not cur.get('_fresh') else dict(cur.get('state') or {})
        cur.pop('_fresh', None)
        label = _conns[target]['label']
        out = {'state': st, 'updated': time.time(), 'dev': target, 'label': label, 'active': target}
        _SESSION_FILE.write_text(json.dumps(out))
    _send(target, {'t': 'cmd', 'a': 'takeover', 'state': st, 'play': bool(st.get('playing'))})
    _broadcast(out)


def _mark_gone(dev):
    """A device dropped. After a short grace (page refresh) an active one counts as stopped."""
    _gone.pop(dev, None)
    with _session_lock:
        cur = _load_session()
        if not cur or cur.get('active') != dev or dev in _conns:
            return
        st = _extrapolated(cur)
        st['playing'] = False
        out = dict(cur, state=st, updated=time.time(), active=None)
        _SESSION_FILE.write_text(json.dumps(out))
    _broadcast(out)


def register(sock):
    from shared import ws_is_authenticated

    @sock.route('/api/music/connect')
    def music_connect(ws):
        # The HTTP auth gate already ran on the upgrade request (same-origin WebSockets carry the
        # login cookie, so the session token never has to appear in the URL or the request log).
        if not ws_is_authenticated(getattr(ws, 'environ', {})):
            try:
                ws.close()
            except Exception:
                pass
            return
        dev, label, lock = None, '', threading.Lock()
        try:
            while True:
                raw = ws.receive(timeout=60)
                if raw is None:                      # 60 s of silence: the client pings every 20 s
                    break
                try:
                    m = json.loads(raw)
                except ValueError:
                    continue
                t = m.get('t')
                if t == 'hello':
                    dev = str(m.get('dev') or '')[:60]
                    label = str(m.get('label') or 'Browser')[:60]
                    if not dev:
                        break
                    with _conn_lock:
                        old = _conns.get(dev)
                        # a "controller" (e.g. the KDE media-widget companion) can send commands but never plays audio
                        _conns[dev] = {'ws': ws, 'label': label, 'lock': lock, 'ctl': str(m.get('role') or '') == 'controller'}
                    g = _gone.pop(dev, None)
                    if g:
                        g.cancel()
                    if old and old['ws'] is not ws:
                        try:
                            old['ws'].close()
                        except Exception:
                            pass
                    with _session_lock:
                        sess = _load_session() or {}
                    _send(dev, _state_msg(sess))
                    _broadcast(sess, skip=dev)       # everyone else learns about the new device
                elif not dev:
                    continue
                elif t == 'ping':
                    _send(dev, {'t': 'pong'})
                elif t == 'state':
                    if _conns.get(dev, {}).get('ctl'):
                        continue                       # controllers never report playback
                    try:
                        res = _report(dev, label, m)
                    except _Bad as e:
                        res = {'ok': False, 'error': str(e)}
                    _send(dev, dict(res, t='ack'))
                elif t == 'cmd':
                    with _session_lock:
                        sess = _load_session() or {}
                    act = _effective_active(sess)
                    if act and act != dev and _send(act, {'t': 'cmd', 'a': m.get('a'), 'v': m.get('v'), 'state': m.get('state'), 'from': dev}):
                        continue
                    _send(dev, {'t': 'nodevice', 'cmd': m.get('a')})
                elif t == 'blocked':                 # the active device's browser refused to start audio
                    _send(str(m.get('to') or ''), {'t': 'blocked', 'dev': dev})
                elif t == 'transfer':
                    target = str(m.get('to') or '')
                    with _session_lock:
                        sess = _load_session() or {}
                    act = _effective_active(sess)
                    if target not in _conns or _conns[target].get('ctl') or target == act:
                        continue
                    if m.get('q') and act != dev and (not act or act not in _conns):
                        try:                         # the sender is showing a song and nobody is playing: that song is what moves
                            _report(dev, label, m, force=True)
                            with _session_lock:
                                cur = _load_session() or {}
                                cur['_fresh'] = True
                                _SESSION_FILE.write_text(json.dumps(cur))
                        except _Bad:
                            pass
                    if act and act in _conns:
                        _send(act, {'t': 'cmd', 'a': 'handoff', 'to': target})
                        tm = threading.Timer(2.5, _finalize_transfer, args=(target,))
                        old = _pending.pop(target, None)
                        if old:
                            old.cancel()
                        _pending[target] = tm
                        tm.start()
                    else:
                        _finalize_transfer(target)
                elif t == 'handoff':                 # exact position from the device that is giving up playback
                    target = str(m.get('to') or '')
                    try:
                        _report(dev, label, m, force=True)
                        with _session_lock:
                            cur = _load_session() or {}
                            cur['_fresh'] = True
                            _SESSION_FILE.write_text(json.dumps(cur))
                    except _Bad:
                        pass
                    if target in _pending:
                        _finalize_transfer(target)
        except Exception:
            pass
        finally:
            if dev:
                with _conn_lock:
                    mine = _conns.get(dev) and _conns[dev]['ws'] is ws
                    if mine:
                        _conns.pop(dev, None)
                if mine:
                    tm = threading.Timer(_GONE_GRACE, _mark_gone, args=(dev,))
                    _gone[dev] = tm
                    tm.start()
                    _broadcast(None)
