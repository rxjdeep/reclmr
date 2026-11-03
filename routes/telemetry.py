"""Telemetry, app usage, and logs routes."""
from flask import Blueprint, jsonify, request, Response
import json, time, re, threading
from shared import TELEMETRY_DIR, USAGE_FILE, LOG_FILE, _read_logs

bp = Blueprint('telemetry', __name__)
_usage_lock = threading.Lock()
USAGE_MAX = 5000

@bp.route('/api/telemetry/app-usage', methods=['GET', 'POST'])
def app_usage():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        app_id = str(data.get('app_id', 'unknown'))[:64]
        action = data.get('action', 'open')
        if action not in ('open', 'close'):
            action = 'open'
        try:
            duration = max(0, min(int(float(data.get('duration', 0))), 86400))
        except (TypeError, ValueError):
            duration = 0
        entry = {
            'app_id': app_id,
            'action': action,
            'duration': duration,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        with _usage_lock:     # one writer at a time: two tabs posting together used to be able to corrupt the file
            log = []
            if USAGE_FILE.exists():
                try:
                    log = json.loads(USAGE_FILE.read_text())
                except Exception:
                    log = []
            log.append(entry)
            log = log[-USAGE_MAX:]    # it used to grow forever
            tmp = USAGE_FILE.with_suffix('.tmp')
            tmp.write_text(json.dumps(log))
            tmp.replace(USAGE_FILE)
        return jsonify({'ok': True, 'entry': entry})

    # GET - aggregated stats
    log = []
    if USAGE_FILE.exists():
        try:
            log = json.loads(USAGE_FILE.read_text())
        except Exception:
            log = []

    per_app = {}
    total_opens = 0
    today = time.strftime('%Y-%m-%d')
    today_stats = {}

    for e in log:
        aid = e.get('app_id', 'unknown')
        ts = e.get('timestamp', '')
        action = e.get('action', '')
        dur = e.get('duration', 0)

        if aid not in per_app:
            per_app[aid] = {'opens': 0, 'total_time': 0}
        if action == 'open':
            per_app[aid]['opens'] += 1
            total_opens += 1
        if action == 'close':
            per_app[aid]['total_time'] += dur

        if ts.startswith(today):
            if aid not in today_stats:
                today_stats[aid] = {'opens': 0, 'total_time': 0}
            if action == 'open':
                today_stats[aid]['opens'] += 1
            if action == 'close':
                today_stats[aid]['total_time'] += dur

    return jsonify({
        'total_opens': total_opens,
        'per_app': per_app,
        'today': today_stats,
    })


# ─── API: Logs ─────────────────────────────────────────────────

@bp.route('/api/logs')
def get_logs():
    limit = request.args.get('limit', 100, type=int)
    return jsonify(_read_logs(limit=limit))

@bp.route('/api/logs/export')
def export_logs():
    logs = _read_logs(limit=100000)
    text = '\n'.join(f"[{l['timestamp']}] {l['level']}: {l['message']}" for l in logs)
    return Response(
        text,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename="reclmr-logs.txt"'},
    )

# ─── API: Telemetry Export ────────────────────────────────────
@bp.route('/api/telemetry/export')
def export_telemetry():
    log = []
    if USAGE_FILE.exists():
        try:
            log = json.loads(USAGE_FILE.read_text())
        except Exception:
            log = []
    return Response(
        json.dumps(log, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename="telemetry-usage.json"'},
    )
