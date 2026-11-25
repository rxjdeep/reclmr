#!/usr/bin/env python3
"""Keep the artist tag of new songs separated, so Navidrome (and reclmr) see several artists, not one long name.

Navidrome splits "A; B", "A & B" and "A / B" itself, but not "A/B", "A, B", "A feat. B" or "A vs. B". This watches the music folder and rewrites those
in files that are new to "A; B". Only the artist and album-artist tags are touched, never the audio. Every change is appended to
tagfix.log (old and new value), so it can be undone.

  python3 scripts/tagfix_watcher.py                 watch (the service does this); only files that were not there when it first started
  python3 scripts/tagfix_watcher.py "path/Song.m4a" fix just these files, once
  python3 scripts/tagfix_watcher.py --since 2d      files modified in the last 2 days (m / h / d), once
  python3 scripts/tagfix_watcher.py --all --dry-run show what it would change in the whole library
  python3 scripts/tagfix_watcher.py --all --once    fix the whole library once

Names that look like several artists but are one ("AC/DC", "Tyler, The Creator") are listed in KEEP below and in tagfix_keep.txt (one per line).
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent
MUSIC = Path(os.environ.get('RECLMR_MUSIC_DIR') or '/media/samsung_ssd/music')
STATE = Path(os.environ.get('RECLMR_TAGFIX_STATE') or _HERE / 'tagfix_state.json')
LOG = Path(os.environ.get('RECLMR_TAGFIX_LOG') or _HERE / 'tagfix.log')
KEEP_FILE = Path(os.environ.get('RECLMR_TAGFIX_KEEP') or _HERE / 'tagfix_keep.txt')
EXTS = {'.mp3', '.m4a', '.flac', '.ogg', '.opus', '.wma', '.aac'}
SETTLE = 20            # seconds a file must stay unchanged first (a download may still be writing it)
EVERY = 30             # seconds between looks at the folder

KEEP = {
    'AC/DC', 'Tyler, The Creator', 'Earth, Wind & Fire', 'Earth, Wind and Fire', 'Crosby, Stills, Nash & Young', 'Crosby, Stills & Nash',
    'Emerson, Lake & Palmer', 'Peter, Paul and Mary', 'Fear, and Loathing in Las Vegas', 'Christ Church Cathedral Choir, Oxford',
    'Probable Cauz Breaks/Jungle/DnB',
}


def load_keep():
    keep = {k.casefold() for k in KEEP}
    try:
        for line in KEEP_FILE.read_text(encoding='utf-8').splitlines():
            if line.strip() and not line.startswith('#'):
                keep.add(line.strip().casefold())
    except OSError:
        pass
    return keep


def split_artist(name, keep):
    """The name with its artists separated by "; ", or None when it should stay as it is."""
    if not name or name.casefold() in keep or ':' in name:        # (a name with a drive letter or path in it is a tagging accident, not artists)
        return None
    if not re.search(r'(?<=\S)/(?=\S)|,\s+(?!and\b|&)|\s(?:feat\.?|ft\.?|featuring|vs\.?)\s', name, re.I):
        return None                                                     # nothing Navidrome cannot split itself ("A; B", "A & B", "A / B")
    t = name
    t = re.sub(r'\s+(?:feat\.?|ft\.?|featuring)\s+', '; ', t, flags=re.I)
    t = re.sub(r'\s+vs\.?\s+', '; ', t, flags=re.I)
    t = re.sub(r'\s*/\s*', '; ', t)
    t = re.sub(r',\s+(?!and\b|&)', '; ', t, flags=re.I)             # "Fear, and Loathing" is a name; "A, B" is two artists
    t = re.sub(r'(?:;\s*){2,}', '; ', t).strip(' ;')
    return t if t != name and t else None


def read_tags(path):
    import mutagen
    return mutagen.File(str(path), easy=True)


def fix_file(path, keep, dry):
    """Returns the changes made (or that would be made) to one file: [(field, old, new)]."""
    try:
        f = read_tags(path)
    except Exception:
        return []
    if f is None or f.tags is None:
        return []
    changes = []
    for field in ('artist', 'albumartist'):
        try:
            vals = f.tags.get(field)
        except Exception:
            vals = None
        if not vals:
            continue
        old = vals[0] if len(vals) == 1 else None                       # several values in one tag are already separated
        new = split_artist(old, keep) if old else None
        if new:
            changes.append((field, old, new))
            if not dry:
                f.tags[field] = [new]
    if changes and not dry:
        f.save()
    return changes


def audio_files():
    for dp, _dn, fn in os.walk(MUSIC):
        for n in fn:
            if os.path.splitext(n)[1].lower() in EXTS:
                yield os.path.join(dp, n)


def parse_age(s):
    m = re.fullmatch(r'(\d+)\s*([mhd])', s.strip().lower())
    if not m:
        raise SystemExit('--since wants something like 30m, 6h or 2d')
    return int(m.group(1)) * {'m': 60, 'h': 3600, 'd': 86400}[m.group(2)]


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return None


def save_state(st):
    try:
        tmp = STATE.with_suffix('.tmp')
        tmp.write_text(json.dumps(st))
        tmp.replace(STATE)
    except OSError:
        pass


def log(rec):
    try:
        with LOG.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except OSError:
        pass


def sweep(keep, dry, state, since=None):
    """One look at the folder. Watching (since is None): a file is looked at once, when it first shows up (a file's modification time says little:
    a copy of the whole library gives every file the same one). With `since`: files modified after that time. `since=0`: every file."""
    known = state.setdefault('known', {})
    now = time.time()
    n = 0
    try:
        files = list(audio_files())
    except OSError:
        return 0                                                        # the drive is away: try again next time
    if not files:
        return 0
    if since is None and not known:                                     # first start: what is here already is not new
        for p in files:
            known[p] = 1
        return 0
    for p in files:
        try:
            mt = os.stat(p).st_mtime
        except OSError:
            continue
        if since is None:
            if p in known or now - mt < SETTLE:
                continue
        elif mt < since:
            continue
        ch = fix_file(p, keep, dry)
        for field, old, new in ch:
            n += 1
            print('%s%s [%s] %r -> %r' % ('(dry run) ' if dry else '', os.path.relpath(p, MUSIC), field, old, new), flush=True)
            if not dry:
                log({'t': int(now), 'file': p, 'field': field, 'old': old, 'new': new})
        if not dry:
            known[p] = 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*', help='fix just these files, once')
    ap.add_argument('--all', action='store_true', help='every file, not only new ones')
    ap.add_argument('--since', help='files modified this long ago or later (30m, 6h, 2d)')
    ap.add_argument('--once', action='store_true', help='look once and stop')
    ap.add_argument('--dry-run', action='store_true', help='show changes, write nothing')
    a = ap.parse_args()
    keep = load_keep()
    if a.files:
        n = 0
        for f in a.files:
            p = f if os.path.isabs(f) else os.path.join(MUSIC, f)
            for field, old, new in fix_file(p, keep, a.dry_run):
                n += 1
                print('%s%s [%s] %r -> %r' % ('(dry run) ' if a.dry_run else '', f, field, old, new))
                if not a.dry_run:
                    log({'t': int(time.time()), 'file': p, 'field': field, 'old': old, 'new': new})
        print('%d tag%s %s' % (n, '' if n == 1 else 's', 'would change' if a.dry_run else 'changed'))
        return
    state = load_state() or {}
    if a.all or a.since:
        n = sweep(keep, a.dry_run, {}, 0 if a.all else time.time() - parse_age(a.since))
        print('%d tag%s %s' % (n, '' if n == 1 else 's', 'would change' if a.dry_run else 'changed'))
        return
    if a.dry_run or a.once:
        n = sweep(keep, a.dry_run, state)
        if not a.dry_run:
            save_state(state)
        print('%d tag%s %s' % (n, '' if n == 1 else 's', 'would change' if a.dry_run else 'changed'))
        return
    print('watching %s' % MUSIC, flush=True)
    while True:
        try:
            before = len(state.get('known', {}))
            n = sweep(keep, False, state)
            if n or len(state.get('known', {})) != before:
                save_state(state)
        except Exception as e:                                          # a bad file must not stop the watcher
            print('error:', e, file=sys.stderr, flush=True)
        time.sleep(EVERY)


if __name__ == '__main__':
    main()
