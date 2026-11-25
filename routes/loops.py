"""Saved A–B loops: named parts of a song ("guitar solo", 1:31 – 1:58) kept on the server, so every device has them."""
import json
import re
import threading
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request

bp = Blueprint('loops', __name__)
_FILE = Path(__file__).resolve().parent.parent / 'music_loops.json'
_lock = threading.Lock()
_MAX_PER_SONG = 30


def _load():
    try:
        d = json.loads(_FILE.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d):
    tmp = _FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(d))
    tmp.replace(_FILE)


def _song(v):
    return v if isinstance(v, str) and 0 < len(v) <= 600 else None


@bp.route('/api/music/loops')
def loops_get():
    f = _song(request.args.get('f'))
    if not f:
        return jsonify({'error': 'bad request'}), 400
    return jsonify({'loops': _load().get(f, [])})


@bp.route('/api/music/loops', methods=['POST'])
def loops_add():
    b = request.get_json(silent=True) or {}
    f = _song(b.get('f'))
    try:
        a, e = float(b.get('a')), float(b.get('b'))
    except (TypeError, ValueError):
        return jsonify({'error': 'bad request'}), 400
    name = re.sub(r'\s+', ' ', str(b.get('name') or '')).strip()[:60]
    if not f or not (0 <= a < e < 1e6):
        return jsonify({'error': 'bad request'}), 400
    with _lock:
        d = _load()
        lst = d.setdefault(f, [])
        if len(lst) >= _MAX_PER_SONG:
            return jsonify({'error': 'too many loops on this song'}), 400
        lst.append({'id': uuid.uuid4().hex[:10], 'name': name or 'Loop %d' % (len(lst) + 1), 'a': round(a, 2), 'b': round(e, 2)})
        _save(d)
        return jsonify({'loops': lst})


@bp.route('/api/music/loops', methods=['DELETE'])
def loops_delete():
    b = request.get_json(silent=True) or {}
    f, lid = _song(b.get('f')), str(b.get('id') or '')
    if not f or not lid:
        return jsonify({'error': 'bad request'}), 400
    with _lock:
        d = _load()
        lst = [x for x in d.get(f, []) if x.get('id') != lid]
        if lst:
            d[f] = lst
        else:
            d.pop(f, None)
        _save(d)
        return jsonify({'loops': lst})
