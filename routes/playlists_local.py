"""Playlists as plain .m3u8 files: what the music player uses when Navidrome is not set up.

One file per playlist in `playlists/` (or RECLMR_PLAYLISTS_DIR). It is the standard format, so there is nothing to
migrate or back up specially: copy the folder, sync it, open it in any other player. Entries are written as absolute
paths (what other players expect); the player itself names a song by its path inside the music folder, so both forms
are read. A file dropped into the folder shows up as a playlist.

    #EXTM3U
    #PLAYLIST:Road trip
    #EXTINF:215,Artist - Title
    /home/you/Music/Artist/Title.flac
"""
import json
import os
import re
import threading
from collections import Counter
from pathlib import Path

import shared

_lock = threading.RLock()
_PID = re.compile(r'^[a-z0-9][a-z0-9-]{0,79}$')
_APP = Path(__file__).resolve().parent.parent


def pl_dir():
    d = Path(os.environ.get('RECLMR_PLAYLISTS_DIR') or _APP / 'playlists')
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def valid_pid(pid):
    return isinstance(pid, str) and bool(_PID.match(pid))


def _file(pid):
    return pl_dir() / (pid + '.m3u8')


def _slug(name):
    s = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:60].strip('-')
    return s or 'playlist'


def _roots():
    base = Path(shared.MUSIC_DIR)
    out = [str(base).rstrip('/') + '/']
    try:
        out.append(str(base.resolve()).rstrip('/') + '/')
    except OSError:
        pass
    return out


def _to_id(line):
    """The player's name for the song a playlist line points at: its path inside the music folder."""
    line = line.strip().replace('\\', '/')
    for root in _roots():
        if line.startswith(root):
            return line[len(root):]
    if line.startswith('./'):
        line = line[2:]
    return None if line.startswith('/') or re.match(r'^[A-Za-z]:/', line) else line      # a path outside the music folder is not ours


def _read(pid):
    f = _file(pid)
    try:
        text = f.read_text(encoding='utf-8-sig', errors='replace')
    except OSError:
        return None
    name, ids = '', []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#PLAYLIST:'):
            name = line[len('#PLAYLIST:'):].strip()
        elif not line.startswith('#'):
            i = _to_id(line)
            if i:
                ids.append(i)
    return {'name': name or pid.replace('-', ' '), 'ids': ids, 'mtime': int(f.stat().st_mtime)}


def _index():
    """Lengths and titles from the library's saved tag index (see routes/music.py), to write the #EXTINF lines."""
    try:
        from routes.music import _INDEX_FILE
        data = json.loads(_INDEX_FILE.read_text())
        return {k: v['r'] for k, v in data.items() if isinstance(v, dict) and 'r' in v}
    except (OSError, ValueError):
        return {}


def _write(pid, name, ids):
    idx = _index()
    base = str(Path(shared.MUSIC_DIR)).rstrip('/')
    lines = ['#EXTM3U', '#PLAYLIST:' + name.replace('\n', ' ')]
    for i in ids:
        r = idx.get(i) or {}
        label = ' - '.join(x for x in (r.get('ar'), r.get('t')) if x) or Path(i).stem
        lines += ['#EXTINF:%d,%s' % (round(r.get('d') or 0) or -1, label.replace('\n', ' ')), base + '/' + i]
    f = _file(pid)
    tmp = f.with_suffix('.tmp')
    tmp.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    tmp.replace(f)


def known(ident):
    """A song that is really in the music folder (the only things a playlist may hold)."""
    from routes.music import _safe_music_path
    p = _safe_music_path(ident)
    return bool(p and p.is_file())


def all_playlists():
    """[{id, name, ids, mtime}] for every playlist file, newest change first."""
    out = []
    with _lock:
        for f in pl_dir().glob('*.m3u8'):
            if valid_pid(f.stem):
                r = _read(f.stem)
                if r:
                    out.append(dict(r, id=f.stem))
    return sorted(out, key=lambda p: -p['mtime'])


def listing(durations):
    """What the library response carries for playlists: id, name, track count, cover id and length."""
    res = []
    for p in all_playlists():
        have = [i for i in p['ids'] if i in durations]
        res.append({'id': p['id'], 'name': p['name'], 'n': len(have), 'c': '', 'd': round(sum(durations[i] for i in have))})
    return res


def entries(pid):
    """The song ids of a playlist (only songs that still exist), or None if there is no such playlist."""
    with _lock:
        r = _read(pid) if valid_pid(pid) else None
    return None if r is None else [i for i in r['ids'] if known(i)]


def create(name, ids=()):
    with _lock:
        base, pid, n = _slug(name), '', 1
        pid = base
        while _file(pid).exists():
            n += 1
            pid = '%s-%d' % (base, n)
        _write(pid, name, [i for i in ids if known(i)])
    return pid


def rename(pid, name):
    with _lock:
        r = _read(pid) if valid_pid(pid) else None
        if r is None:
            return False
        _write(pid, name, r['ids'])
    return True


def delete(pid):
    with _lock:
        if not valid_pid(pid) or not _file(pid).exists():
            return False
        _file(pid).unlink()
    return True


def add(pid, ident, index=None):
    """(position or None, found): None when the song is already in the list."""
    with _lock:
        r = _read(pid) if valid_pid(pid) else None
        if r is None or not known(ident):
            return None, False
        if ident in r['ids']:
            return None, True
        at = len(r['ids']) if index is None or index >= len(r['ids']) else index
        r['ids'].insert(at, ident)
        _write(pid, r['name'], r['ids'])
    return at, True


def remove(pid, ident):
    """Indices that were removed, or None for a missing playlist."""
    with _lock:
        r = _read(pid) if valid_pid(pid) else None
        if r is None:
            return None
        idx = [i for i, x in enumerate(r['ids']) if x == ident]
        if idx:
            _write(pid, r['name'], [x for x in r['ids'] if x != ident])
    return idx


def set_order(pid, ids, base):
    """'ok', 'missing' or 'stale' (the list is not the one the page started from, or `ids` would add something it did not have)."""
    with _lock:
        r = _read(pid) if valid_pid(pid) else None
        if r is None:
            return 'missing'
        if len(r['ids']) != base or Counter(ids) - Counter(r['ids']):
            return 'stale'
        _write(pid, r['name'], ids)
    return 'ok'


def membership(ident):
    return [p['id'] for p in all_playlists() if ident in p['ids']]


def in_any():
    return sorted({i for p in all_playlists() for i in p['ids'] if known(i)})
