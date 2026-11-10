"""Laptop volume from the phone.

A browser cannot change the system volume, so a tiny agent (scripts/volume_agent.py, Python standard library only) runs on the laptop. It long-polls
this server; the phone's two buttons queue a step for it. The agent applies the step with whatever the laptop has (macOS osascript; Linux wpctl,
pactl or amixer) and reports the new level on its next poll."""
import threading
import time

from flask import Blueprint, jsonify, request

bp = Blueprint('volume', __name__)

_cv = threading.Condition()
_agents = {}                 # name -> {'seen', 'level', 'muted', 'platform', 'backend', 'cmds': []}
_ONLINE = 40                 # an agent that has not polled for this long (s) is offline
_WAIT = 25                   # long-poll length (s)
_STEP_MAX = 25


def _name(v):
    v = str(v or '').strip()[:40]
    return v or 'laptop'


def _view():
    now = time.time()
    return [{'name': n, 'level': a['level'], 'muted': a['muted'], 'platform': a['platform'], 'backend': a['backend'],
             'online': now - a['seen'] < _ONLINE} for n, a in sorted(_agents.items())]


@bp.route('/api/volume/agent/poll', methods=['POST'])
def volume_poll():
    """The laptop agent: reports its level and waits for a command."""
    b = request.get_json(silent=True) or {}
    name = _name(b.get('name'))
    deadline = time.time() + _WAIT
    with _cv:
        a = _agents.setdefault(name, {'cmds': [], 'n': 0, 'level': None, 'muted': False, 'platform': '', 'backend': ''})
        lvl = b.get('level')
        a['level'] = int(lvl) if isinstance(lvl, (int, float)) and 0 <= lvl <= 100 else a['level']
        a['muted'] = bool(b.get('muted'))
        a['platform'] = str(b.get('platform') or '')[:20]
        a['backend'] = str(b.get('backend') or '')[:20]
        a['seen'] = time.time()
        a['n'] += 1                                        # one report per poll
        _cv.notify_all()                                   # a phone waiting for the new level
        while not a['cmds'] and time.time() < deadline:
            _cv.wait(timeout=max(0.1, deadline - time.time()))
            a['seen'] = time.time()
        cmds, a['cmds'] = a['cmds'], []
    return jsonify({'cmds': cmds})


@bp.route('/api/volume/agents', methods=['GET'])
def volume_agents():
    with _cv:
        return jsonify({'agents': _view()})


@bp.route('/api/volume/step', methods=['POST'])
def volume_step():
    """The phone: nudge the laptop volume up or down. Waits briefly for the new level."""
    b = request.get_json(silent=True) or {}
    try:
        step = int(b.get('step'))
    except (TypeError, ValueError):
        return jsonify({'error': 'bad step'}), 400
    step = max(-_STEP_MAX, min(_STEP_MAX, step))
    if not step:
        return jsonify({'error': 'bad step'}), 400
    now = time.time()
    with _cv:
        live = [n for n, a in _agents.items() if now - a['seen'] < _ONLINE]
        want = _name(b.get('name')) if b.get('name') else None
        name = want if want in live else (live[0] if len(live) == 1 and not want else None)
        if not name:
            return jsonify({'error': 'no laptop connected'}), 409
        a = _agents[name]
        before = a['n']
        a['cmds'].append({'a': 'step', 'v': step})
        _cv.notify_all()
        end = time.time() + 3                              # the agent reports its new level on its next poll
        while a['n'] == before and time.time() < end:
            _cv.wait(timeout=0.2)
        return jsonify({'ok': True, 'agent': name, 'level': a['level'], 'muted': a['muted']})
