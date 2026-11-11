#!/usr/bin/env python3
"""reclmr laptop volume agent. Lets the phone's volume buttons change THIS machine's system volume.

Standard library only; works on Linux (PipeWire/PulseAudio via wpctl or pactl, or ALSA via amixer) and macOS (osascript).
Run it on the laptop, in a terminal or as a login/startup item:

    RECLMR_URL=https://your-server python3 volume_agent.py        # first run asks for the passcode once, then remembers a session

Options: --url, --name (default: the machine's hostname), --pin-env (read the passcode from RECLMR_PIN instead of asking).
It only ever sets the output volume between 0 and 100 %; it makes no other change to the machine."""
import argparse
import getpass
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TOKEN_FILE = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'reclmr-volume' / 'session'


def _run(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout


# ─── backends: each is (name, get() -> (level 0-100, muted), set(level, unmute)) ───
def _mac():
    def get():
        out = _run('osascript', '-e', 'output volume of (get volume settings)').strip()
        mute = _run('osascript', '-e', 'output muted of (get volume settings)').strip()
        return int(out), mute == 'true'

    def set_(level, unmute=True):
        _run('osascript', '-e', 'set volume output volume %d' % level)
        if unmute:
            _run('osascript', '-e', 'set volume without output muted')
    return get, set_


def _wpctl():
    def get():
        out = _run('wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@')            # "Volume: 0.45 [MUTED]"
        m = re.search(r'Volume:\s*([\d.]+)', out)
        return int(round(float(m.group(1)) * 100)), '[MUTED]' in out

    def set_(level, unmute=True):
        _run('wpctl', 'set-volume', '@DEFAULT_AUDIO_SINK@', '%d%%' % level)
        if unmute:
            _run('wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', '0')
    return get, set_


def _pactl():
    def get():
        out = _run('pactl', 'get-sink-volume', '@DEFAULT_SINK@')
        m = re.search(r'(\d+)%', out)
        return int(m.group(1)), 'yes' in _run('pactl', 'get-sink-mute', '@DEFAULT_SINK@')

    def set_(level, unmute=True):
        _run('pactl', 'set-sink-volume', '@DEFAULT_SINK@', '%d%%' % level)
        if unmute:
            _run('pactl', 'set-sink-mute', '@DEFAULT_SINK@', '0')
    return get, set_


def _amixer():
    def get():
        out = _run('amixer', 'get', 'Master')
        m = re.search(r'\[(\d+)%\]', out)
        return int(m.group(1)), '[off]' in out

    def set_(level, unmute=True):
        _run('amixer', '-q', 'set', 'Master', '%d%%' % level)
        if unmute:
            _run('amixer', '-q', 'set', 'Master', 'unmute')
    return get, set_


def pick_backend():
    """The first backend that is installed AND answers."""
    cands = []
    if sys.platform == 'darwin':
        cands = [('osascript', _mac, 'osascript')]
    else:
        cands = [('wpctl', _wpctl, 'wpctl'), ('pactl', _pactl, 'pactl'), ('amixer', _amixer, 'amixer')]
    for name, make, exe in cands:
        if not shutil.which(exe):
            continue
        get, set_ = make()
        try:
            get()
        except Exception:
            continue
        return name, get, set_
    sys.exit('No volume control found (looked for %s). On Linux install pipewire-pulse/pulseaudio-utils or alsa-utils.' % ', '.join(c[0] for c in cands))


# ─── talking to the server ───
def call(url, path, body, token, timeout=40):
    req = urllib.request.Request(url.rstrip('/') + path, data=json.dumps(body).encode(), method='POST')
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b'{}')


def login(url, use_env):
    pin = os.environ.get('RECLMR_PIN') if use_env else None
    pin = pin or getpass.getpass('reclmr passcode: ')
    d = call(url, '/api/auth/login', {'pin': pin}, None, 15)
    tok = d.get('session', '')
    if tok:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(tok)
        os.chmod(TOKEN_FILE, 0o600)
    return tok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--url', default=os.environ.get('RECLMR_URL', 'http://localhost:8899'))
    ap.add_argument('--name', default=socket.gethostname().split('.')[0])
    ap.add_argument('--pin-env', action='store_true', help='take the passcode from RECLMR_PIN (for unattended starts)')
    a = ap.parse_args()
    backend, get, set_ = pick_backend()
    print('volume agent "%s" on %s using %s -> %s' % (a.name, platform.system(), backend, a.url), flush=True)
    try:
        token = TOKEN_FILE.read_text().strip()
    except OSError:
        token = ''
    fails = 0
    while True:
        try:
            level, muted = get()
            d = call(a.url, '/api/volume/agent/poll', {'name': a.name, 'level': level, 'muted': muted, 'platform': platform.system(), 'backend': backend}, token)
            fails = 0
            for c in d.get('cmds', []):
                if c.get('a') == 'set':
                    new = max(0, min(100, int(c.get('v', 0))))
                    set_(new, unmute=new > 0)
                elif c.get('a') == 'step':
                    cur, _ = get()
                    new = max(0, min(100, cur + int(c.get('v', 0))))
                    set_(new, unmute=new > 0)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                try:
                    token = login(a.url, a.pin_env)
                    continue
                except Exception as ex:
                    print('login failed: %s' % ex, flush=True)
            fails += 1
            time.sleep(min(30, 2 * fails))
        except Exception as ex:
            fails += 1
            if fails in (1, 10):
                print('server not reachable (%s); retrying' % ex, flush=True)
            time.sleep(min(30, 2 * fails))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
