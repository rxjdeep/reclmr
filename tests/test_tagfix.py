import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location('tagfix_watcher', Path(__file__).resolve().parent.parent / 'scripts' / 'tagfix_watcher.py')
tf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tf)
KEEP = tf.load_keep()


def test_unseparated_artists_are_split():
    s = lambda n: tf.split_artist(n, KEEP)
    assert s('Galantis/Zack Martino') == 'Galantis; Zack Martino'
    assert s('Rain Man/Krysta Youngs/T-Mass') == 'Rain Man; Krysta Youngs; T-Mass'
    assert s('KR$NA, Umair, Mukesh') == 'KR$NA; Umair; Mukesh'
    assert s('Pharrell ft. Daddy Yankee') == 'Pharrell; Daddy Yankee'
    assert s('E-40 featuring The Click') == 'E-40; The Click'
    assert s('DJ Spooky Vs. Dave Lombardo') == 'DJ Spooky; Dave Lombardo'


def test_single_names_and_already_separated_ones_are_left_alone():
    s = lambda n: tf.split_artist(n, KEEP)
    for n in ('AC/DC', 'Tyler, The Creator', 'Fear, and Loathing in Las Vegas', 'Mac Miller', 'Silent Attack & nuvoices',
              'VISUAL ARTS / Key', 'Dr. Dre; Snoop Dogg', 'C:/18hzr/breakcore', ''):
        assert s(n) is None, n
