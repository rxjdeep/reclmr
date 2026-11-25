"""Library health: what is wrong with the library's tags, and a button to fix what can be fixed.

It reads the library (not the files) for most checks, so it is quick; only FLAC / Ogg files are opened (for the missing release date).
Fixes are worked out on the server from the library itself (never from file names the browser sends) and are logged to tagfix.log like the tag watcher's.
"""
import json
import os
import re
import threading
import time
from collections import defaultdict

from flask import Blueprint, jsonify

import tagtools

bp = Blueprint('health', __name__)
_cache = {'ts': 0.0, 'data': None}
_lock = threading.Lock()                 # the cached result
_fix_lock = threading.Lock()             # one fix at a time
_TTL = 600


def _norm(s):
    return re.sub(r'\W+', ' ', str(s or '').lower()).strip()


def _local(t):
    """The file on this machine for a library song, or None."""
    from routes import music
    rel = music._nd_paths.get(t['f']) if music._nd_conf() else t['f']
    if not rel:
        return None
    p = music._safe_music_path(rel)
    return p if p and p.is_file() else None


def split_albums(tracks):
    """Albums Navidrome holds in several pieces: [{al, ar, members: [track]}]. (The same album name and album artist under more than one album id.)"""
    by = defaultdict(lambda: defaultdict(list))
    for t in tracks:
        if t.get('al') and t.get('li'):
            by[(_norm(t['al']), _norm(t.get('aa') or t.get('ar')))][t['li']].append(t)
    out = []
    for parts in by.values():
        if len(parts) > 1:
            members = [x for ts in parts.values() for x in ts]
            out.append({'al': members[0]['al'], 'ar': members[0].get('aa') or members[0].get('ar') or '', 'parts': [ts for ts in parts.values()], 'members': members})
    return sorted(out, key=lambda a: a['al'].lower())


def release_plan(album):
    """[(file, release date)] to give the FLAC / Ogg songs of a split album: the full date its other songs have (when they agree on one)."""
    dates, files = [], []
    for t in album['members']:
        p = _local(t)
        if not p:
            continue
        d, rd = tagtools.release_dates(p)
        files.append((t, p))
        if len(rd) >= 10:
            dates.append(rd)
    years = {d[:4] for d in dates}
    if not dates or len(years) != 1:
        return []
    target = max(set(dates), key=dates.count)
    return [(p, target) for t, p in files if str(t.get('sx') or '').lower() in ('flac', 'opus', 'ogg') and tagtools.apply_release_date(p, target, dry=True)]


def scan():
    """All the findings: [{kind, title, help, fixable, count, items: [...]}]."""
    from routes import music
    tracks = music._library_data().get('tracks', [])
    keep = tagtools.load_keep()
    unsplit, no_album = [], []
    seen = defaultdict(list)
    for t in tracks:
        title, artist = t.get('t') or '', t.get('ar') or ''
        new = tagtools.split_artist(artist, keep) or tagtools.split_artist(t.get('aa') or '', keep)
        if new:
            unsplit.append({'f': t['f'], 't': title, 'ar': artist, 'to': tagtools.split_artist(artist, keep) or new})
        if not t.get('al'):
            no_album.append({'f': t['f'], 't': title, 'ar': artist})
        first = (t.get('as') or [[0, artist]])[0][1]
        seen[(_norm(first), _norm(title))].append(t)
    dups = []
    for (_a, _t), ts in seen.items():
        if len(ts) < 2 or not _t:
            continue
        ts.sort(key=lambda x: x.get('d') or 0)
        groups, cur = [], [ts[0]]
        for x in ts[1:]:                                                # copies are about the same length: a remix or a live take is not a duplicate
            if abs((x.get('d') or 0) - (cur[-1].get('d') or 0)) <= 3:
                cur.append(x)
            else:
                groups.append(cur)
                cur = [x]
        groups.append(cur)
        for g in groups:
            if len(g) > 1:
                dups.append({'f': g[0]['f'], 't': g[0].get('t') or '', 'ar': g[0].get('ar') or '', 'n': len(g),
                             'where': [(x.get('al') or 'no album') + ' · ' + str(x.get('sx') or '') for x in g][:4]})

    split, fixable_files = [], 0
    for a in split_albums(tracks):
        n_fix = len(release_plan(a))
        fixable_files += n_fix
        split.append({'f': a['members'][0]['f'], 't': a['al'], 'ar': a['ar'],
                      'to': ' + '.join('%d × %s' % (len(ts), '/'.join(sorted({str(x.get('sx') or '?') for x in ts}))) for ts in a['parts']) + (' · %d file(s) can be fixed' % n_fix if n_fix else '')})

    def group(kind, title, help_, items, fixable):
        return {'kind': kind, 'title': title, 'help': help_, 'fixable': fixable, 'count': len(items), 'items': items[:12]}
    out = [
        group('unsplit', 'Artists not separated', 'The artist tag joins several names in a way Navidrome cannot split ("A/B", "A, B", "A feat. B"). The fix rewrites it as "A; B".', unsplit, True),
        group('split', 'Albums split in pieces', 'One album shows up as several in Navidrome, usually because a FLAC has no release date while its album-mates do (the Self Care problem). The fix copies the release date onto those FLAC files (%d now).' % fixable_files, split, fixable_files > 0),
        group('noalbum', 'Songs with no album', 'Nothing to fix automatically: add an album tag, or leave them as singles.', no_album, False),
        group('dups', 'Possible duplicates', 'The same artist, title and length more than once. Nothing is deleted for you.', dups, False),
    ]
    return {'checked': int(time.time()), 'songs': len(tracks), 'groups': out}


def _log(rec):
    try:
        with open(tagtools.Path(__file__).resolve().parent.parent / 'tagfix.log', 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except OSError:
        pass


def fix(kind):
    """Apply one kind of fix to every song that needs it. Returns the number of tags changed."""
    from routes import music
    keep = tagtools.load_keep()
    tracks = music._library_data().get('tracks', [])
    n = 0
    if kind == 'unsplit':
        for t in tracks:
            p = _local(t)
            if not p or not (tagtools.split_artist(t.get('ar') or '', keep) or tagtools.split_artist(t.get('aa') or '', keep)):
                continue
            for field, old, new in tagtools.fix_file(p, keep, False):
                n += 1
                _log({'t': int(time.time()), 'file': str(p), 'field': field, 'old': old, 'new': new})
    elif kind == 'split':
        for a in split_albums(tracks):
            for p, target in release_plan(a):
                if tagtools.apply_release_date(p, target, dry=False):
                    n += 1
                    _log({'t': int(time.time()), 'file': str(p), 'field': 'releasedate', 'old': '', 'new': target})
    return n


@bp.route('/api/music/health')
def health_get():
    from routes import drive
    if not drive._S['ok']:
        return jsonify({'error': 'The music drive is offline.'}), 503
    with _lock:
        if _cache['data'] and time.time() - _cache['ts'] < _TTL:
            return jsonify(_cache['data'])
    data = scan()
    with _lock:
        _cache.update(ts=time.time(), data=data)
    return jsonify(data)


@bp.route('/api/music/health/fix/<kind>', methods=['POST'])
def health_fix(kind):
    if kind not in ('unsplit', 'split'):
        return jsonify({'error': 'unknown fix'}), 400
    from routes import drive, music
    if not drive._S['ok']:
        return jsonify({'error': 'The music drive is offline.'}), 503
    if not _fix_lock.acquire(blocking=False):
        return jsonify({'error': 'busy'}), 409
    try:
        n = fix(kind)
        with _lock:
            _cache.update(ts=0.0, data=None)
    finally:
        _fix_lock.release()
    if n and music._nd_conf():
        try:
            music._nd_get('startScan')                                   # Navidrome reads the changed files; the library on screen follows
        except Exception:
            pass
    music._invalidate()
    return jsonify({'changed': n})
