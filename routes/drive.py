"""Is the music drive readable? When it drops out, keep the library on screen instead of letting it empty out.

An external drive that resets itself (a bad cable or port) makes Navidrome's next scan fail and mark every loose song "missing", so they vanish from the app
until a scan runs again. So: a monitor looks at the folder every 15 s; while the drive is away (and until Navidrome has scanned again after it came back)
the last good copy of the library is served with a notice, and when the drive returns a scan is started so the songs come back by themselves.
"""
import json
import os
import threading
import time
from pathlib import Path

from flask import Blueprint, jsonify

import shared

bp = Blueprint('drive', __name__)

_GOOD_FILE = Path(__file__).resolve().parent.parent / 'library_good.json'
_EVERY = 15
_S = {'ok': True, 'since': 0.0, 'healing': False, 'last_offline': 0.0, 'good': None, 'good_n': 0, 'saved': 0.0}
_lock = threading.Lock()


def probe(path, timeout=5):
    """True when the folder can be listed (a dropped drive answers "input/output error", or hangs)."""
    res = {}

    def go():
        try:
            with os.scandir(path) as it:
                res['first'] = next(it, None)
            res['ok'] = True
        except OSError:
            res['ok'] = False
    t = threading.Thread(target=go, daemon=True)
    t.start()
    t.join(timeout)
    if not res.get('ok'):
        return False
    return res.get('first') is not None or not _S['good_n']        # an empty folder is a missing drive, once there has been a library


def _clock(ts):
    return time.strftime('%H:%M', time.localtime(ts))


def notice():
    s = _S
    if not s['ok']:
        return ('Music drive offline since %s: songs cannot play right now. Your library is kept as it was and comes back by itself once the drive is '
                'reachable (check the cable, or remount it).' % _clock(s['since']))
    if s['healing']:
        return 'The music drive is back. Refreshing the library…'
    return ''


def guard(data):
    """The library to show: `data`, unless the drive is away or just came back (or the song count fell off a cliff soon after it was away)."""
    s = _S
    n = len(data.get('tracks') or [])
    with _lock:
        suspicious = (not s['ok']) or s['healing'] or (s['good_n'] and n < 0.85 * s['good_n'] and time.time() - s['last_offline'] < 1800)
        if suspicious and s['good']:
            out = dict(s['good'])
            out['error'] = notice() or 'Some songs are missing from the library right now (the music drive was offline a moment ago). Showing the last complete list.'
            out['offline'] = True
            return out
        if n and s['ok'] and not s['healing']:
            s['good'], s['good_n'] = data, n
            _save_good(data, n)
    return data


def _save_good(data, n):
    if time.time() - _S['saved'] < 600 or 'pytest' in __import__('sys').modules:         # (tests must not write runtime files)
        return
    _S['saved'] = time.time()
    try:
        tmp = _GOOD_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(data))
        tmp.replace(_GOOD_FILE)
    except OSError:
        pass


def _load_good():
    try:
        d = json.loads(_GOOD_FILE.read_text())
        if d.get('tracks'):
            _S['good'], _S['good_n'] = d, len(d['tracks'])
    except (OSError, ValueError, AttributeError):
        pass


def _heal():
    """The drive is back: have Navidrome scan again (the failed scan marked songs missing), then drop the copies we kept."""
    from . import music
    try:
        time.sleep(8)                                                # let the drive settle
        if music._nd_conf():
            music._nd_get('startScan')
            time.sleep(5)
            for _ in range(120):                                     # up to 20 minutes
                if not music._nd_get('getScanStatus').get('scanStatus', {}).get('scanning'):
                    break
                time.sleep(10)
    except Exception as e:
        print('[drive] rescan after the drive came back failed:', e, flush=True)
    finally:
        with _lock:
            _S['healing'] = False
        music._invalidate()
        print('[drive] library refreshed', flush=True)


def check_once(path=None):
    """One look; returns True when the state changed."""
    ok = probe(path or shared.MUSIC_DIR)
    with _lock:
        was = _S['ok']
        if ok == was:
            return False
        _S['ok'] = ok
        if not ok:
            _S['since'] = _S['last_offline'] = time.time()
            print('[drive] music drive went offline', flush=True)
        else:
            _S['healing'] = True
            print('[drive] music drive is back', flush=True)
    if ok:
        threading.Thread(target=_heal, daemon=True).start()
    else:
        try:
            from . import music
            music._invalidate()
        except Exception:
            pass
    return True


def _loop():
    while True:
        try:
            check_once()
        except Exception as e:
            print('[drive] monitor error:', e, flush=True)
        time.sleep(_EVERY)


@bp.route('/api/music/drive')
def music_drive():
    return jsonify({'ok': _S['ok'], 'since': _S['since'], 'healing': _S['healing'], 'msg': notice()})


if 'pytest' not in __import__('sys').modules:
    _load_good()
    threading.Thread(target=_loop, daemon=True).start()
