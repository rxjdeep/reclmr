"""Tag fixes shared by the tag watcher (scripts/tagfix_watcher.py) and the Library health page (routes/health.py)."""
import os
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
KEEP_FILE = Path(os.environ.get('RECLMR_TAGFIX_KEEP') or _HERE / 'tagfix_keep.txt')

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


def release_date_fix(path, dry=True):
    """FLAC / Ogg files carry DATE (a year) but players such as Navidrome group albums by RELEASEDATE, which m4a gets from the same field.
    Returns the date that is (or would be) copied into RELEASEDATE, or None when the file does not need it."""
    try:
        import mutagen
        f = mutagen.File(str(path))
    except Exception:
        return None
    if f is None or f.tags is None or type(f).__name__ not in ('FLAC', 'OggOpus', 'OggVorbis'):
        return None
    keys = {k.lower(): k for k in f.tags.keys()}
    if 'date' not in keys or 'releasedate' in keys:
        return None
    val = f.tags[keys['date']]
    val = val[0] if isinstance(val, list) else str(val)
    if not val or not re.match(r'^\d{4}', val):
        return None
    if not dry:
        f.tags['RELEASEDATE'] = [val]
        f.save()
    return val


def release_dates(path):
    """(DATE, RELEASEDATE) of a file, each '' when missing (an m4a's date counts as both: that is how it is read)."""
    try:
        import mutagen
        f = mutagen.File(str(path), easy=True)
    except Exception:
        return '', ''
    if f is None or f.tags is None:
        return '', ''
    def one(k):
        try:
            v = f.tags.get(k)
        except Exception:
            return ''
        return str(v[0]) if v else ''
    date = one('date')
    return date, (one('releasedate') or (date if type(f).__name__ in ('MP4', 'EasyMP4', 'MP3', 'EasyID3') else ''))


def apply_release_date(path, target, dry=True):
    """Give a FLAC / Ogg file the release date its album-mates have. True when it was (or would be) changed."""
    try:
        import mutagen
        f = mutagen.File(str(path))
    except Exception:
        return False
    if f is None or f.tags is None or type(f).__name__ not in ('FLAC', 'OggOpus', 'OggVorbis'):
        return False
    keys = {k.lower(): k for k in f.tags.keys()}
    if 'releasedate' in keys:
        return False
    own = f.tags[keys['date']][0] if 'date' in keys and f.tags[keys['date']] else ''
    if own and own[:4] != target[:4]:                                    # a different year: another release of the album, not the same one
        return False
    if not dry:
        f.tags['RELEASEDATE'] = [target]
        if not own:
            f.tags['DATE'] = [target]
        f.save()
    return True
